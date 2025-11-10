# mcp_server.py  – unified and clean
from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Optional
import requests, os, json, asyncio
from openai import OpenAI
from db import init_db, get_stock_overview, connect, update_stock

app = FastAPI(title="Stock Assistant MCP Server")

BACKEND_URL = "http://localhost:8000"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

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
SYSTEM_PROMPT = """
You are a smart store inventory assistant for retail operations.

TOOLS YOU CAN TRIGGER:
1) get_low_stock(store_id)
2) transfer_stock(product, from_store, to_store, qty)

You MUST convert natural language into tool parameters when possible.

Examples:
"show low stock of store 103"
→ {"action":"get_low_stock","args":{"store_id":103}}

"transfer 5 milk from store 101 to 103"
→ {"action":"transfer_stock","args":{"product":"milk","from_store":101,"to_store":103,"qty":5}}

If input is casual conversation, return:
{"action":"none","reply":"<natural reply>"}
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

    history = "\n".join(SESSION_MEMORY[session_id])

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":f"History:\n{history}\nUser: {user_msg}"}
        ]
    )

    try:
        tool = json.loads(resp.choices[0].message.content)
    except Exception:
        reply = resp.choices[0].message.content
        add_to_memory(session_id, f"Assistant: {reply}")
        return ChatResponse(reply=reply)

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

    decision = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":f"History:\n{history}\nUser: {user_msg}"}
        ]
    )
    try:
        tool = json.loads(decision.choices[0].message.content)
    except Exception:
        tool = {"action": "none", "reply": decision.choices[0].message.content}

    # No tool: stream natural reply
    if tool["action"] == "none":
        async def stream_text():
            reply = tool["reply"]
            add_to_memory(session_id, f"Assistant: {reply}")
            for ch in reply:
                yield ch
                await asyncio.sleep(0.01)
        return StreamingResponse(stream_text(), media_type="text/event-stream")

    # Tool call
    result = run_tool(tool, session_id).reply
    async def stream_tool():
        add_to_memory(session_id, f"Assistant: {result}")
        for ch in result:
            yield ch
            await asyncio.sleep(0.01)
    return StreamingResponse(stream_tool(), media_type="text/event-stream")


# ----------------------------
# Tool runner
# ----------------------------
def run_tool(tool, session_id="default") -> ChatResponse:
    action = tool.get("action")
    args = tool.get("args", {})

    try:
        if action == "get_low_stock":
            r = requests.get(f"{BACKEND_URL}/low_stock/{args['store_id']}")
            data = r.json()
            reply = "Low stock items:\n" + "\n".join(
                f"- {i['product']} ({i['qty']})"
                for i in data.get("low_stock_items", [])
            )
            add_to_memory(session_id, f"Assistant: {reply}")
            return ChatResponse(reply=str(reply))

        if action == "transfer_stock":
            args = tool.get("args", {})

            # 🔧 Normalize keys for backend schema
            payload = {
                "product_name": args.get("product") or args.get("product_name"),
                "from_store": args.get("from_store"),
                "to_store": args.get("to_store"),
                "quantity": args.get("qty") or args.get("quantity"),
            }
            r = requests.post(f"{BACKEND_URL}/transfer_stock", json=payload)
            try:
                data = r.json()
                if isinstance(data, dict):
                    reply = data.get("detail") or json.dumps(data)
                elif isinstance(data, list):
                    reply = json.dumps(data)
                else:
                    reply = str(data)
            except Exception as e:
                reply = f"Error calling transfer API: {e}"

            add_to_memory(session_id, f"Assistant: {reply}")
            return ChatResponse(reply=str(reply))

        reply = f"Unknown action: {action}"
        add_to_memory(session_id, f"Assistant: {reply}")
        return ChatResponse(reply=str(reply))

    except Exception as e:
        reply = f"Unhandled error in run_tool: {e}"
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

