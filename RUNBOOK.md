# Backend Runbook

## Purpose
Use this runbook to start, verify, and troubleshoot the backend side of the Stock Assistant POC.

## Services
- `src.main:app`
  REST backend on port `8000`
- `src.mcp_server:app`
  assistant server on port `3000`

## Local Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start Commands
Terminal 1:
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2:
```bash
uvicorn src.mcp_server:app --host 0.0.0.0 --port 3000 --reload
```

## Health Checks
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:3000/health
```

Expected:
- `8000` returns a simple backend health response
- `3000` returns assistant service info and whether it is using Gemini or local fallback

## Demo Data Notes
- SQLite data is seeded on startup by `init_db()`
- main demo routes:
  - Parent Store `101`
  - PFS `201` and `204`
  - Staff Canteen `301`
- recommendation logic is local and deterministic

## Recommendation Flow
The transfer recommendation engine is a deterministic rules layer over seeded SQLite history.

### API
The app calls:

```bash
GET /transfer_recommendations?from_store=101&to_store=301&transfer_type=CANTEEN
```

### Inputs
- `from_store`
- `to_store`
- `transfer_type`
- fixed lookback window: `30` days

### Query
`src/db.py:get_transfer_recommendations()` runs a grouped query on `transfer_history` and joins `stock` for source inventory checks.

```sql
SELECT
    th.product_name,
    COUNT(*) AS frequency,
    AVG(th.quantity) AS avg_qty,
    MIN(th.quantity) AS min_qty,
    MAX(th.quantity) AS max_qty,
    MAX(th.created_at) AS last_transferred_at,
    CAST(julianday('now') - julianday(MAX(th.created_at)) AS REAL) AS days_since_last,
    s.quantity AS source_stock,
    s.reorder_level AS reorder_level
FROM transfer_history th
JOIN stock s
  ON s.store_id = th.from_store
 AND lower(trim(s.product_name)) = lower(trim(th.product_name))
WHERE th.from_store = ?
  AND th.to_store = ?
  AND upper(th.transfer_type) = ?
  AND th.created_at >= ?
GROUP BY th.product_name, s.quantity, s.reorder_level
HAVING COUNT(*) >= 3
```

### Post-query filters
- drop products with no usable average quantity
- drop products with `quantity_spread_ratio > 0.75`
- drop products where `source_stock <= reorder_level`

### Quantity formula
```python
available_to_transfer = max(source_stock - reorder_level, 0)
suggested_qty = min(max(int(round(avg_qty)), 1), available_to_transfer)
```

### Score formula
```python
frequency_score = min(frequency / 6.0, 1.0)
recency_score = max(0.0, 1.0 - (days_since_last / 30))
score = round(((frequency_score * 0.7) + (recency_score * 0.3)) * consistency_multiplier, 2)
```

### Confidence
- `high`: `score >= 0.8` and `frequency >= 4`
- `medium`: `score >= 0.55`
- `low`: everything else that passed the filters

### Response fields
- `product`: product name
- `suggested_qty`: recommended transfer quantity
- `frequency`: how many times the route transferred the product
- `score`: numeric strength from `0` to `1`
- `confidence`: `high`, `medium`, or `low`
- `reason`: short human-readable explanation

### Example interpretation
```text
Milk 1L
High
Suggested qty 18 • score 0.87 • moved 5 times
frequently transferred recently
```

This means:
- the route repeated often
- the transfers were recent
- quantities were stable enough
- source stock could support the transfer

### AI boundary
- recommendation scoring is local only
- Gemini is used for chat/routing when available
- if Gemini returns `429` or is unavailable, the MCP server uses local fallback logic

## Useful Endpoints
```bash
curl "http://127.0.0.1:8000/stores"
curl "http://127.0.0.1:8000/products"
curl "http://127.0.0.1:8000/transfer_recommendations?from_store=101&to_store=204&transfer_type=PFS"
curl "http://127.0.0.1:3000/tool/get_transfer_recommendations?from_store=101&to_store=301&transfer_type=CANTEEN"
```

## Verification
Syntax check:
```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile src/db.py src/main.py src/mcp_server.py src/schemas.py
```

## Common Issues
- `3000/health` returns `404`
  - you are likely running a stale server from another repo copy or another working directory
- assistant replies are generic or old
  - restart the MCP server on `3000`
- recommendation output looks empty
  - verify source/destination pair matches seeded history

## POC Guardrails
- keep replies concise for mobile UI
- keep recommendation logic deterministic
- use AI for explanation, routing, and guidance
- do not add heavy infrastructure or production-only complexity
