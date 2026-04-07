# schemas.py - lightweight response models for the POC
from pydantic import BaseModel
from typing import List, Optional

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
    score: float
    confidence: str
    reason: str

class TransferRecommendationResponse(BaseModel):
    from_store: int
    to_store: int
    transfer_type: str
    suggestions: List[TransferSuggestion]


class StoreDirectoryItem(BaseModel):
    store_id: int
    store_name: str
    store_type: str
    parent_store_id: Optional[int] = None


class StoreDirectoryResponse(BaseModel):
    items: List[StoreDirectoryItem]


class ProductListResponse(BaseModel):
    items: List[str]
