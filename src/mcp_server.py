# mcp_server.py  – unified and clean
from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Optional
import requests, os, json, asyncio
from openai import OpenAI
from src.db import init_db, get_stock_overview, connect, update_stock, get_unique_product_names

app = FastAPI(title="Stock Assistant MCP Server")

import google.generativeai as genai

BACKEND_URL = "http://localhost:8000"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️ WARNING: GEMINI_API_KEY not set!")

genai.configure(api_key=GEMINI_API_KEY)
# Using gemini-2.0-flash-001 (Specific version)
model = genai.GenerativeModel('gemini-2.0-flash-001')

# ----------------------------
# Session memory
# ----------------------------
SESSION_MEMORY: dict[str, list[str]] = {}

def add_to_memory(session_id: str, text: str):
    SESSION_MEMORY.setdefault(session_id, []).append(text)
    SESSION_MEMORY[session_id] = SESSION_MEMORY[session_id][-10:]

# ----------------------------
# Intent routing prompt
# ----------------------------
# ----------------------------
# Intent routing prompt
# ----------------------------
# ----------------------------
# Intent routing prompt
# ----------------------------
BASE_SYSTEM_PROMPT = """
You are a smart store inventory assistant for retail operations.

TOOLS YOU CAN TRIGGER:
1) get_low_stock(store_id, product=null)
2) transfer_stock(product, from_store, to_store, qty)
3) get_product_info(product, store_id=null)

VALID PRODUCTS:
{product_list}

RULES:
- You MUST convert natural language into tool parameters when possible.
- AUTO-CORRECT typos to the nearest VALID PRODUCT from the list.
  (e.g., "soaps" -> "Soap", "cokes" -> "Coke 500ml")
- If the user implies "any store" or "where can I find", set "store_id": null.
- If the user asks about a specific store (e.g., "in store 101"), set "store_id": 101.
- USE HISTORY to resolve implicit arguments. If user asks "is it low?", check previous messages for the store/product being discussed.

Examples:
"show low stock of store 103"
→ {{"action":"get_low_stock","args":{{"store_id":103}}}}

"transfer 5 milk from store 101 to 103"
→ {{"action":"transfer_stock","args":{{"product":"Milk 1L","from_store":101,"to_store":103,"qty":5}}}}

"How many cokes do we have?"
→ {{"action":"get_product_info","args":{{"product":"Coke 500ml","store_id":null}}}}

"Price of bread in store 102"
→ {{"action":"get_product_info","args":{{"product":"Bread","store_id":102}}}}

(Context: User previously asked "Where is Soap?" -> Found in Store 103)
"Is it low in stock?"
→ {{"action":"get_low_stock","args":{{"store_id":103, "product":"Soap"}}}}

If input is casual conversation, return:
{{"action":"none","reply":"<natural reply>"}}
"""

# ----------------------------
# Chat models
# ----------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    reply: str

# ----------------------------
# Chat endpoints
# ----------------------------
@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    user_msg = body.message
    session_id = body.session_id
    add_to_memory(session_id, f"User: {user_msg}")

    # 1. Fetch valid products dynamically
    try:
        products = get_unique_product_names()
        product_list_str = ", ".join(products)
    except Exception:
        product_list_str = "None available"

    # 2. Inject into prompt
    system_prompt = BASE_SYSTEM_PROMPT.format(product_list=product_list_str)

    history = "\n".join(SESSION_MEMORY[session_id])

    # Construct complete prompt
    full_prompt = f"{system_prompt}\n\nHistory:\n{history}\nUser: {user_msg}"

    try:
        resp = model.generate_content(
            full_prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        content = resp.text
        tool = json.loads(content)
    except Exception as e:
        print(f"Gemini Error: {e}")
        return ChatResponse(reply="Sorry, I'm having trouble connecting to the AI.")

    if tool.get("action") == "none":
        reply = tool.get("reply", "")
        add_to_memory(session_id, f"Assistant: {reply}")
        return ChatResponse(reply=reply)

    return run_tool(tool, session_id)


@app.post("/chat_stream")
async def chat_stream(body: ChatRequest):
    user_msg = body.message
    session_id = body.session_id
    add_to_memory(session_id, f"User: {user_msg}")
    history = "\n".join(SESSION_MEMORY[session_id])

    # 1. Fetch valid products dynamically
    try:
        products = get_unique_product_names()
        product_list_str = ", ".join(products)
    except Exception:
        product_list_str = "None available"

    # 2. Inject into prompt
    system_prompt = BASE_SYSTEM_PROMPT.format(product_list=product_list_str)

    full_prompt = f"{system_prompt}\n\nHistory:\n{history}\nUser: {user_msg}"

    try:
        # We don't stream the decision part effectively with tools in this specific architecture
        # because we need the full JSON to decide whether to run a tool or not.
        # So we await the full response first.
        resp = model.generate_content(
            full_prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        content = resp.text
        tool = json.loads(content)
    except Exception as e:
        print(f"Gemini Error: {e}")
        tool = {"action": "none", "reply": "Sorry, service disruption."}

    # No tool: stream natural reply
    if tool["action"] == "none":
        async def stream_text():
            reply = tool.get("reply", "")
            add_to_memory(session_id, f"Assistant: {reply}")
            # Simulate streaming since we already have the full text from the JSON mode generation
            chunk_size = 5 
            for i in range(0, len(reply), chunk_size):
                yield reply[i:i+chunk_size]
                await asyncio.sleep(0.01)
        return StreamingResponse(stream_text(), media_type="text/event-stream")

    # Tool call
    result = run_tool(tool, session_id).reply
    async def stream_tool():
        add_to_memory(session_id, f"Assistant: {result}")
        # Return full result at once or chunk it
        yield result
    return StreamingResponse(stream_tool(), media_type="text/event-stream")


# ----------------------------
# Tool Endpoints (Direct Access)
# ----------------------------
@app.get("/tool/get_low_stock")
def tool_get_low_stock(store_id: int, threshold: int = 10):
    """Proxy for get_low_stock tool."""
    # We can reuse the logic in run_tool or call the backend directly
    # Reusing run_tool logic for consistency requires mocking the tool dict
    tool = {
        "action": "get_low_stock",
        "args": {"store_id": store_id}
    }
    # run_tool returns a ChatResponse, but the Android app expects the raw JSON structure
    # So we should probably hit the backend directly like run_tool does, but return the raw data
    try:
        r = requests.get(f"{BACKEND_URL}/low_stock/{store_id}?threshold={threshold}")
        return r.json()
    except Exception as e:
        return {"error": str(e)}

@app.post("/tool/transfer_stock")
def tool_transfer_stock(body: dict = Body(...)):
    """Proxy for transfer_stock tool."""
    # The Android app sends: product_name, from_store, to_store, quantity
    # Backend expects: product_name, from_store, to_store, quantity
    try:
        r = requests.post(f"{BACKEND_URL}/transfer_stock", json=body)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# ----------------------------
# Tool runner
# ----------------------------
# ----------------------------
# Tool runner
# ----------------------------




def run_tool(tool, session_id="default") -> ChatResponse:
    action = tool.get("action")
    args = tool.get("args", {})

    try:
        if action == "get_low_stock":
            args = tool.get("args", {})
            store_id = args['store_id']
            product = args.get("product")

            params = {"threshold": args.get("threshold", 10)}
            if product:
                params["product"] = product
            
            r = requests.get(f"{BACKEND_URL}/low_stock/{store_id}", params=params)
            data = r.json()
            items = data.get("low_stock_items", [])

            if product:
                if not items:
                    reply = f"I couldn't find '{product}' in Store {store_id}."
                else:
                    item = items[0]
                    status = "LOW on stock" if item.get("is_low") else "sufficiently stocked"
                    reply = f"In Store {store_id}, {item['product']} is {status}. We have {item['qty']} units left."
            else:
                # General check
                if not items:
                    reply = f"Good news! Store {store_id} has no low stock items right now."
                else:
                    items_str = ", ".join(f"{i['product']} ({i['qty']})" for i in items)
                    reply = f"Attention: The following items are low in Store {store_id}: {items_str}."
            
            add_to_memory(session_id, f"Assistant: {reply}")
            return ChatResponse(reply=reply)

        if action == "transfer_stock":
            args = tool.get("args", {})
            payload = {
                "product_name": args.get("product") or args.get("product_name"),
                "from_store": args.get("from_store"),
                "to_store": args.get("to_store"),
                "quantity": args.get("qty") or args.get("quantity"),
            }
            r = requests.post(f"{BACKEND_URL}/transfer_stock", json=payload)
            try:
                data = r.json()
                detail = data.get("detail") or str(data)
                reply = f"Transfer complete: {detail}"
            except Exception as e:
                reply = f"There was an issue processing that transfer: {e}"

            add_to_memory(session_id, f"Assistant: {reply}")
            return ChatResponse(reply=reply)

        if action == "get_product_info":
            args = tool.get("args", {})
            product = args.get("product")
            store_id = args.get("store_id")

            params = {"product_name": product}
            if store_id:
                params["store_id"] = store_id
            
            r = requests.get(f"{BACKEND_URL}/product_details", params=params)
            data = r.json().get("results", [])
            
            if not data:
                if store_id:
                    reply = f"I couldn't find any information for '{product}' in Store {store_id}."
                else:
                    reply = f"I searched all stores but couldn't find '{product}'."
            else:
                if store_id:
                    item = data[0]
                    reply = f"Store {item['store_id']} has {item['qty']} units of {item['product']} ({item['uom']}). The price is ${item['price']}."
                else:
                    rows_str = [f"Store {i['store_id']} has {i['qty']} {i['uom']} (${i['price']})" for i in data]
                    reply = f"I found '{product}' in these locations:\n" + "\n".join(rows_str)

            add_to_memory(session_id, f"Assistant: {reply}")
            return ChatResponse(reply=reply)

        reply = f"Unknown action: {action}"
        add_to_memory(session_id, f"Assistant: {reply}")
        return ChatResponse(reply=str(reply))

    except Exception as e:
        reply = f"System Error: {e}"
        # We don't naturalize system errors implies debugging
        add_to_memory(session_id, f"Assistant: {reply}")
        return ChatResponse(reply=str(reply))



# ===========================================================
# Stock overview / live update endpoints  (moved from db.py)
# ===========================================================
subscribers: set[asyncio.Queue] = set()

def notify_clients(data: dict):
    msg = json.dumps(data)
    for q in list(subscribers):
        q.put_nowait(msg)

@app.get("/stock/overview")
def stock_overview():
    """Return total items, low stock, expiring soon counts."""
    return get_stock_overview()

@app.get("/stock/store/{store_id}")
def stock_by_store(store_id: int):
    """Return all products and quantities for a specific store."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT product_name, quantity, category, uom, price, expiry_date
        FROM stock
        WHERE store_id=?
    """, (store_id,))
    rows = cur.fetchall()
    conn.close()

    return {
        "store_id": store_id,
        "items": [
            {
                "product": r[0],
                "quantity": r[1],
                "category": r[2],
                "uom": r[3],
                "price": r[4],
                "expiry_date": r[5],
                "storeId": store_id
            } for r in rows
        ]
    }

@app.post("/stock/update")
def stock_update(data: dict = Body(...)):
    """Update stock quantity then notify SSE subscribers."""
    product = data["product_name"]
    store = data["store_id"]
    qty = data["quantity"]
    update_stock(product, store, qty)
    notify_clients({"type": "update", "product": product, "store_id": store, "quantity": qty})
    return {"detail": "Stock updated", "product": product, "store_id": store, "quantity": qty}

@app.get("/stock/live")
async def stock_live():
    """SSE endpoint for live stock changes."""
    async def event_stream():
        q = asyncio.Queue()
        subscribers.add(q)
        try:
            while True:
                msg = await q.get()
                yield f"data: {msg}\n\n"
        finally:
            subscribers.remove(q)
    return StreamingResponse(event_stream(), media_type="text/event-stream")

# ==========================
# 🧩 Ensure DB initialized
# ==========================
@app.on_event("startup")
def startup_event():
    print("🔄 Initializing database...")
    try:
        init_db()
        print("✅ Database ready.")
    except Exception as e:
        print(f"❌ DB init failed: {e}")

