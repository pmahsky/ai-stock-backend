# mcp_server.py - local AI orchestration for the Stock Assistant POC
import asyncio
import json
import os
import re
from typing import Optional

import requests
from fastapi import Body, FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.db import (
    connect,
    get_stock_overview,
    get_store_directory,
    get_unique_product_names,
    init_db,
    update_stock,
)

app = FastAPI(title="Stock Assistant MCP Server")

try:
    import google.generativeai as genai
except ImportError:
    genai = None

BACKEND_URL = "http://localhost:8000"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY and genai is not None:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-001")
else:
    model = None
    print("⚠️ WARNING: Gemini SDK or API key unavailable, using local intent fallback.")

SESSION_MEMORY: dict[str, list[str]] = {}


def add_to_memory(session_id: str, text: str):
    SESSION_MEMORY.setdefault(session_id, []).append(text)
    SESSION_MEMORY[session_id] = SESSION_MEMORY[session_id][-10:]


BASE_SYSTEM_PROMPT = """
You are a smart store inventory assistant for retail operations.

TOOLS YOU CAN TRIGGER:
1) get_low_stock(store_id, product=null)
2) get_product_info(product, store_id=null)
3) get_transfer_recommendations(from_store, to_store, transfer_type)
4) open_transfer_assist(from_store=null, to_store=null, transfer_type=null, product=null, qty=null)

VALID STORES:
{store_list}

VALID PRODUCTS:
{product_list}

RULES:
- Convert user requests into tool arguments whenever possible.
- AUTO-CORRECT obvious product typos to the nearest valid product.
- If the user asks what the app can do, how to use it, or says they are new, answer directly with a short onboarding-style reply.
- For transfer planning questions such as "what should I send", "suggest items", "frequent transfers", or "what goes to canteen/PFS", prefer get_transfer_recommendations.
- For direct transfer requests such as "transfer 5 milk to PFS", do NOT execute a transfer in chat. Return open_transfer_assist so the app can open the structured transfer screen.
- If source store is missing for a transfer question, prefer store 101 for this demo.
- If the user says "canteen", use transfer_type CANTEEN and default destination store 301 unless another store is explicit.
- If the user says "PFS", use transfer_type PFS and default destination store 201 unless another store is explicit.
- If the request is missing a critical detail and no safe default exists, ask one short follow-up using action "none".
- Keep replies concise, practical, and UI-oriented.

Examples:
"show low stock of store 103"
-> {{"action":"get_low_stock","args":{{"store_id":103}}}}

"How many cokes do we have?"
-> {{"action":"get_product_info","args":{{"product":"Coke 500ml","store_id":null}}}}

"What should I transfer to the staff canteen?"
-> {{"action":"get_transfer_recommendations","args":{{"from_store":101,"to_store":301,"transfer_type":"CANTEEN"}}}}

"Open transfer for Central PFS"
-> {{"action":"open_transfer_assist","args":{{"from_store":101,"to_store":201,"transfer_type":"PFS"}}}}

"Transfer 5 milk from store 101 to PFS"
-> {{"action":"open_transfer_assist","args":{{"from_store":101,"to_store":201,"transfer_type":"PFS","product":"Milk 1L","qty":5}}}}

"I am new here. What can you do?"
-> {{"action":"none","reply":"I can help in 4 ways: plan transfers, check low stock, find product details, and explain how each screen works. Try 'suggest products for PFS 204' or 'how does Transfer Assist work?'"}}

"How does Transfer Assist work?"
-> {{"action":"none","reply":"Pick the destination, review AI picks, add manual items if needed, adjust singles or cases, then submit the transfer."}}

If the input is casual conversation, return:
{{"action":"none","reply":"<natural reply>"}}
"""


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class TransferAssistContext(BaseModel):
    from_store: Optional[int] = None
    to_store: Optional[int] = None
    transfer_type: Optional[str] = None
    product: Optional[str] = None
    qty: Optional[int] = None


class ChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None
    transfer_context: Optional[TransferAssistContext] = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mcp_server",
        "mode": "gemini" if model else "local_fallback",
    }


def _store_name(store_id: Optional[int]) -> str:
    if store_id is None:
        return "the selected store"
    for store in get_store_directory():
        if store["store_id"] == store_id:
            return f"{store['store_name']} ({store_id})"
    return f"Store {store_id}"


def _normalize_product(raw_product: Optional[str], valid_products: list[str]) -> Optional[str]:
    if not raw_product:
        return None

    needle = raw_product.strip().lower()
    if not needle:
        return None

    for product in valid_products:
        if needle == product.lower():
            return product

    for product in valid_products:
        product_lower = product.lower()
        singular = needle[:-1] if needle.endswith("s") else needle
        if singular in product_lower or product_lower in needle:
            return product

    return raw_product.strip().title()


def _extract_store_ids(message: str) -> list[int]:
    return [int(match) for match in re.findall(r"\b\d{3}\b", message)]


def _infer_transfer_defaults(message: str, store_ids: list[int]):
    lowered = message.lower()
    transfer_type = None
    to_store = None

    if "canteen" in lowered:
        transfer_type = "CANTEEN"
        to_store = 301
    elif "pfs" in lowered:
        transfer_type = "PFS"
        to_store = 201

    from_store = 101
    if len(store_ids) >= 2:
        from_store, to_store = store_ids[0], store_ids[1]
    elif len(store_ids) == 1:
        if transfer_type:
            to_store = store_ids[0]
        else:
            from_store = store_ids[0]
    elif to_store is None:
        if transfer_type == "CANTEEN":
            to_store = 301
        elif transfer_type == "PFS":
            to_store = 201

    return from_store, to_store, transfer_type


def _route_message_with_rules(message: str, valid_products: list[str]):
    lowered = message.lower().strip()
    store_ids = _extract_store_ids(message)
    qty_match = re.search(r"\b(\d+)\b", lowered)
    qty = int(qty_match.group(1)) if qty_match else None
    product = None

    for candidate in valid_products:
        if candidate.lower() in lowered:
            product = candidate
            break

    if not product and "milk" in lowered:
        product = _normalize_product("milk", valid_products)
    elif not product and "bread" in lowered:
        product = _normalize_product("bread", valid_products)
    elif not product and "chips" in lowered:
        product = _normalize_product("chips", valid_products)
    elif not product and "soap" in lowered:
        product = _normalize_product("soap", valid_products)
    elif not product and "coke" in lowered:
        product = _normalize_product("coke", valid_products)

    if any(
        phrase in lowered
        for phrase in [
            "what can you do",
            "how can you help",
            "i am new",
            "i'm new",
            "new colleague",
            "explain app",
            "what all can be done",
            "show me around",
            "how do i use this app",
        ]
    ):
        return {
            "action": "none",
            "reply": (
                "I can help with transfer planning, low-stock checks, product lookup, and screen guidance. "
                "Try 'suggest products for PFS 204', 'show low stock in store 103', or 'how does Transfer Assist work?'"
            ),
        }

    if any(
        phrase in lowered
        for phrase in [
            "how does transfer assist work",
            "what is transfer assist",
            "how to use transfer assist",
            "explain transfer assist",
        ]
    ):
        return {
            "action": "none",
            "reply": "Pick the destination, review AI picks, add manual items if needed, adjust singles or cases, then submit.",
        }

    if any(
        phrase in lowered
        for phrase in [
            "what can i ask",
            "example prompts",
            "what should i ask",
        ]
    ):
        return {
            "action": "none",
            "reply": "Try: 'suggest products for PFS 204', 'what should I transfer to staff canteen?', 'show low stock in store 103', or 'where is Milk 1L?'",
        }

    if "low stock" in lowered or ("is it low" in lowered and store_ids):
        args = {"store_id": store_ids[0] if store_ids else 101}
        if product:
            args["product"] = product
        return {"action": "get_low_stock", "args": args}

    if any(keyword in lowered for keyword in ["where is", "how many", "price", "have we got"]):
        if product:
            return {
                "action": "get_product_info",
                "args": {
                    "product": product,
                    "store_id": store_ids[0] if store_ids else None,
                },
            }

    if any(keyword in lowered for keyword in ["suggest", "recommend", "frequent", "what should i transfer", "what goes"]):
        from_store, to_store, transfer_type = _infer_transfer_defaults(message, store_ids)
        if transfer_type and to_store:
            return {
                "action": "get_transfer_recommendations",
                "args": {
                    "from_store": from_store,
                    "to_store": to_store,
                    "transfer_type": transfer_type,
                },
            }

    if "transfer" in lowered or "move" in lowered:
        from_store, to_store, transfer_type = _infer_transfer_defaults(message, store_ids)
        return {
            "action": "open_transfer_assist",
            "args": {
                "from_store": from_store,
                "to_store": to_store,
                "transfer_type": transfer_type or "PFS",
                "product": product,
                "qty": qty,
            },
        }

    return {
        "action": "none",
        "reply": "I can help plan transfers, check stock, or find product details. Try asking what should go to PFS or the staff canteen.",
    }


def _route_message(message: str, session_id: str):
    valid_products = get_unique_product_names()
    stores = get_store_directory()
    fallback_tool = _route_message_with_rules(message, valid_products)

    if not model:
        return fallback_tool

    store_list_str = ", ".join(
        f"{store['store_name']} ({store['store_id']}, {store['store_type']})" for store in stores
    )
    product_list_str = ", ".join(valid_products) if valid_products else "None available"
    system_prompt = BASE_SYSTEM_PROMPT.format(
        product_list=product_list_str,
        store_list=store_list_str,
    )

    history = "\n".join(SESSION_MEMORY.get(session_id, []))
    full_prompt = f"{system_prompt}\n\nHistory:\n{history}\nUser: {message}"

    try:
        resp = model.generate_content(
            full_prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        tool = json.loads(resp.text)
        action = tool.get("action")
        reply = (tool.get("reply") or "").strip()

        if action == "none" and (
            reply == "<natural reply>"
            or (fallback_tool.get("action") != "none" and reply)
            or not reply
        ):
            return fallback_tool

        if not action:
            return fallback_tool

        return tool
    except Exception as exc:
        print(f"Gemini Error: {exc}")
        return fallback_tool


def _build_transfer_assist_response(args, reply=None):
    context = TransferAssistContext(
        from_store=args.get("from_store"),
        to_store=args.get("to_store"),
        transfer_type=(args.get("transfer_type") or "PFS").upper(),
        product=args.get("product"),
        qty=args.get("qty"),
    )

    if not reply:
        destination = _store_name(context.to_store)
        if context.product and context.qty:
            reply = (
                f"I've opened Transfer Assist for {destination} and prefilled "
                f"{context.qty} of {context.product}. You can review the quantities before submitting."
            )
        else:
            reply = (
                f"I've opened Transfer Assist for {destination} so you can review the recommendations "
                f"and add any extra items."
            )

    return ChatResponse(
        reply=reply,
        action="open_transfer_assist",
        transfer_context=context,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    user_msg = body.message
    session_id = body.session_id
    add_to_memory(session_id, f"User: {user_msg}")

    tool = _route_message(user_msg, session_id)
    action = tool.get("action")

    if action == "none":
        reply = tool.get("reply", "").strip() or "I’m ready to help with stock and transfer planning."
        add_to_memory(session_id, f"Assistant: {reply}")
        return ChatResponse(reply=reply)

    if action == "open_transfer_assist":
        response = _build_transfer_assist_response(tool.get("args", {}), tool.get("reply"))
        add_to_memory(session_id, f"Assistant: {response.reply}")
        return response

    response = run_tool(tool, session_id)
    add_to_memory(session_id, f"Assistant: {response.reply}")
    return response


@app.post("/chat_stream")
async def chat_stream(body: ChatRequest):
    response = chat(body)

    async def stream_text():
        reply = response.reply
        chunk_size = 10
        for index in range(0, len(reply), chunk_size):
            yield reply[index : index + chunk_size]
            await asyncio.sleep(0.01)

    return StreamingResponse(stream_text(), media_type="text/event-stream")


@app.get("/tool/get_low_stock")
def tool_get_low_stock(store_id: int, threshold: int = 10):
    try:
        r = requests.get(f"{BACKEND_URL}/low_stock/{store_id}", params={"threshold": threshold})
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/tool/get_transfer_recommendations")
def tool_get_transfer_recommendations(from_store: int, to_store: int, transfer_type: str):
    try:
        r = requests.get(
            f"{BACKEND_URL}/transfer_recommendations",
            params={
                "from_store": from_store,
                "to_store": to_store,
                "transfer_type": transfer_type,
            },
        )
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


@app.post("/tool/transfer_stock")
def tool_transfer_stock(body: dict = Body(...)):
    try:
        r = requests.post(f"{BACKEND_URL}/transfer_stock", json=body)
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def run_tool(tool, session_id="default") -> ChatResponse:
    action = tool.get("action")
    args = tool.get("args", {})

    try:
        if action == "get_low_stock":
            store_id = args["store_id"]
            product = args.get("product")
            params = {"threshold": args.get("threshold", 10)}
            if product:
                params["product"] = product

            r = requests.get(f"{BACKEND_URL}/low_stock/{store_id}", params=params)
            items = r.json().get("low_stock_items", [])

            if product:
                if not items:
                    return ChatResponse(
                        reply=f"I couldn’t find {product} in {_store_name(store_id)}."
                    )
                item = items[0]
                if item.get("is_low"):
                    reply = f"{item['product']} is low in {_store_name(store_id)}: {item['qty']} left."
                else:
                    reply = f"{item['product']} is available in {_store_name(store_id)}: {item['qty']} on hand."
                return ChatResponse(reply=reply)

            if not items:
                return ChatResponse(reply=f"No low stock items in {_store_name(store_id)}.")

            items_str = ", ".join(f"{item['product']} ({item['qty']})" for item in items[:5])
            return ChatResponse(reply=f"Low stock in {_store_name(store_id)}: {items_str}.")

        if action == "get_product_info":
            product = args.get("product")
            store_id = args.get("store_id")

            params = {"product_name": product}
            if store_id:
                params["store_id"] = store_id

            r = requests.get(f"{BACKEND_URL}/product_details", params=params)
            data = r.json().get("results", [])

            if not data:
                if store_id:
                    return ChatResponse(
                        reply=f"I couldn’t find {product} in {_store_name(store_id)}."
                    )
                return ChatResponse(
                    reply=f"I couldn’t find any stock records for {product}."
                )

            if store_id:
                item = data[0]
                return ChatResponse(
                    reply=f"{item['product']}: {item['qty']} units in {_store_name(item['store_id'])}, ${item['price']} per {item['uom']}."
                )

            rows_str = ", ".join(
                f"{_store_name(item['store_id'])}: {item['qty']} {item['uom']}" for item in data
            )
            return ChatResponse(reply=f"{product} is available at {rows_str}.")

        if action == "get_transfer_recommendations":
            from_store = args.get("from_store")
            to_store = args.get("to_store")
            transfer_type = (args.get("transfer_type") or "PFS").upper()

            r = requests.get(
                f"{BACKEND_URL}/transfer_recommendations",
                params={
                    "from_store": from_store,
                    "to_store": to_store,
                    "transfer_type": transfer_type,
                },
            )
            suggestions = r.json().get("suggestions", [])

            if not suggestions:
                return ChatResponse(
                    reply=f"No strong repeat pattern for {_store_name(to_store)} yet. Use Transfer Assist to add items manually."
                )

            top_suggestions = suggestions[:3]
            summary = ", ".join(
                f"{item['product']} ({item['suggested_qty']}, {item['confidence']})"
                for item in top_suggestions
            )
            return ChatResponse(
                reply=f"Top picks for {_store_name(to_store)}: {summary}."
            )

        return ChatResponse(reply="I understood the request, but I couldn’t map it to a supported action.")

    except Exception as exc:
        print(f"Tool Error: {exc}")
        return ChatResponse(
            reply="I hit a local service issue while checking that. Please try again in a moment."
        )


subscribers: set[asyncio.Queue] = set()


def notify_clients(data: dict):
    msg = json.dumps(data)
    for queue in list(subscribers):
        queue.put_nowait(msg)


@app.get("/stock/overview")
def stock_overview():
    return get_stock_overview()


@app.get("/stock/store/{store_id}")
def stock_by_store(store_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT product_name, quantity, category, uom, price, expiry_date
        FROM stock
        WHERE store_id = ?
        ORDER BY product_name
        """,
        (store_id,),
    )
    rows = cur.fetchall()
    conn.close()

    return {
        "store_id": store_id,
        "items": [
            {
                "product": row[0],
                "quantity": row[1],
                "category": row[2],
                "uom": row[3],
                "price": row[4],
                "expiry_date": row[5],
                "storeId": store_id,
            }
            for row in rows
        ],
    }


@app.post("/stock/update")
def stock_update(data: dict = Body(...)):
    product = data["product_name"]
    store_id = data["store_id"]
    quantity = data["quantity"]
    update_stock(product, store_id, quantity)
    notify_clients(
        {"type": "update", "product": product, "store_id": store_id, "quantity": quantity}
    )
    return {
        "detail": "Stock updated",
        "product": product,
        "store_id": store_id,
        "quantity": quantity,
    }


@app.get("/stock/live")
async def stock_live():
    async def event_stream():
        queue = asyncio.Queue()
        subscribers.add(queue)
        try:
            while True:
                msg = await queue.get()
                yield f"data: {msg}\n\n"
        finally:
            subscribers.remove(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.on_event("startup")
def startup_event():
    print("🔄 Initializing database...")
    try:
        init_db()
        print("✅ Database ready.")
    except Exception as exc:
        print(f"❌ DB init failed: {exc}")
