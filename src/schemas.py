# schemas.py - placeholder for Pydantic schemas if you want to expand
from pydantic import BaseModel

class LowStockResponse(BaseModel):
    store_id: int
    low_stock_items: list
