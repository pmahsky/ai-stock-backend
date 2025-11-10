from fastapi import FastAPI
from pydantic import BaseModel
from src.db import init_db, get_low_stock, transfer_stock_record
app = FastAPI(title="StockQuery Backend")

class TransferRequest(BaseModel):
    product_name: str
    from_store: int
    to_store: int
    quantity: int

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/low_stock/{store_id}")
def low_stock(store_id: int, threshold: int = 10):
    items = get_low_stock(store_id, threshold)
    return {"store_id": store_id, "low_stock_items": items}

@app.post("/transfer_stock")
def transfer_stock(req: TransferRequest):
    result = transfer_stock_record(req.product_name, req.from_store, req.to_store, req.quantity)
    return {"ok": True, "detail": result}

