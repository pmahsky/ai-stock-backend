from fastapi import FastAPI
from src.db import (
    init_db,
    get_low_stock,
    transfer_stock_record,
    get_transfer_recommendations,
    get_product_details,
    get_store_directory,
    get_unique_product_names,
)
from src.schemas import (
    TransferRequest,
    TransferRecommendationResponse,
    StoreDirectoryResponse,
    ProductListResponse,
)
app = FastAPI(title="StockQuery Backend")


@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/low_stock/{store_id}")
def low_stock(store_id: int, threshold: int = 10, product: str = None):
    items = get_low_stock(store_id, threshold, product)
    return {"store_id": store_id, "low_stock_items": items}

@app.get("/product_details")
def product_details_endpoint(product_name: str, store_id: int = None):
    # If store_id is not passed, it comes as None
    results = get_product_details(product_name, store_id)
    return {"product": product_name, "results": results}


@app.get("/stores", response_model=StoreDirectoryResponse)
def store_directory(q: str = None):
    return {"items": get_store_directory(q)}


@app.get("/products", response_model=ProductListResponse)
def product_directory(q: str = None):
    products = get_unique_product_names()
    if q:
        needle = q.strip().lower()
        products = [product for product in products if needle in product.lower()]
    return {"items": products}

@app.post("/transfer_stock")
def transfer_stock(req: TransferRequest):
    result = transfer_stock_record(req.product_name, req.from_store, req.to_store, req.quantity, req.transfer_type)
    if result == "transfer successful":
        return {"ok": True, "detail": result}
    else:
        return {"ok": False, "detail": result}

@app.get("/transfer_recommendations", response_model=TransferRecommendationResponse)
def recommendations(from_store: int, to_store: int, transfer_type: str):
    suggestions = get_transfer_recommendations(from_store, to_store, transfer_type)
    return {
        "from_store": from_store,
        "to_store": to_store,
        "transfer_type": transfer_type,
        "suggestions": suggestions
    }
