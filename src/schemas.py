# schemas.py - placeholder for Pydantic schemas if you want to expand
from pydantic import BaseModel
from typing import List

class LowStockResponse(BaseModel):
    store_id: int
    low_stock_items: list

class TransferRequest(BaseModel):
    product_name: str
    from_store: int
    to_store: int
    quantity: int
    transfer_type: str = "MANUAL"

class TransferSuggestion(BaseModel):
    product: str
    suggested_qty: int
    frequency: int
    reason: str

class TransferRecommendationResponse(BaseModel):
    from_store: int
    to_store: int
    transfer_type: str
    suggestions: List[TransferSuggestion]
