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

## Recommendation Logic
This POC recommends products by looking at recent transfer history for the exact route the user selected.

### Plain-English Flow
1. User chooses source store, destination store, and transfer type.
2. Backend looks at the last `30` days of transfer history for that exact route.
3. It groups transfers by product and checks:
   - how often the product moved
   - how recent the last transfer was
   - whether the quantities were fairly consistent
   - whether the source store still has enough stock
4. If the product passes the filters, the backend returns it as a recommendation.

### Query Shape
The backend uses a query shaped like:

```sql
SELECT product_name, COUNT(*), AVG(quantity), MIN(quantity), MAX(quantity), MAX(created_at)
FROM transfer_history
WHERE from_store = ?
  AND to_store = ?
  AND transfer_type = ?
  AND created_at >= ?
GROUP BY product_name
HAVING COUNT(*) >= 3
```

### What Happens After the Query
- `suggested_qty` is set to the rounded average transfer quantity
- the quantity is capped by the source store stock minus reorder level
- a score is calculated from frequency and recency
- confidence is labeled as `high`, `medium`, or `low`

### UI Meaning
- `frequency` = how many times this exact route moved the product
- `score` = simple strength number from `0` to `1`
- `confidence` = human-friendly summary of the score
- `reason` = short explanation like `frequently transferred recently`

### Important Guardrails
- no ML model is used for recommendation scoring
- AI is only used for assistant conversation and guidance
- if Gemini is unavailable or quota-limited, the MCP server uses local fallback logic

## Recommendation Logic
The transfer recommendation flow is intentionally simple for the POC.

### Inputs
- `from_store`
- `to_store`
- `transfer_type`

These come from the Transfer Assist screen and are sent to:

```bash
GET /transfer_recommendations?from_store=101&to_store=301&transfer_type=CANTEEN
```

### What the query asks
In plain language, the backend asks:

```text
For this exact route and transfer type, what products were moved repeatedly in the last 30 days,
what quantity was usually moved, and can the source store still spare that stock?
```

### Query behavior
The SQL in `src/db.py:get_transfer_recommendations()`:
- filters to the exact `from_store`, `to_store`, and `transfer_type`
- only checks the last `30` days
- groups by product
- calculates:
  - transfer count
  - average quantity
  - min and max quantity
  - latest transfer date
  - current source stock
  - reorder level
- ignores products moved fewer than `3` times

### Filtering rules
After the query returns grouped rows, Python applies these checks:
- skip products with no usable average quantity
- skip very inconsistent quantity history
  - current rule: `(max_qty - min_qty) / avg_qty > 0.75`
- skip products where source stock cannot spare quantity beyond reorder level

### Suggested quantity
The recommendation quantity is:

```text
rounded historical average, capped by available transferable stock
```

Formula:

```python
available_to_transfer = max(source_stock - reorder_level, 0)
suggested_qty = min(max(int(round(avg_qty)), 1), available_to_transfer)
```

### Score
The score is a lightweight strength signal from `0.0` to `1.0`.

It combines:
- `frequency` as the main signal
- `recency` as the secondary signal
- `consistency` as a multiplier

Formula:

```python
frequency_score = min(frequency / 6.0, 1.0)
recency_score = max(0.0, 1.0 - (days_since_last / 30))

score = ((frequency_score * 0.7) + (recency_score * 0.3)) * consistency_multiplier
```

### Confidence labels
- `high`
  - `score >= 0.8` and `frequency >= 4`
- `medium`
  - `score >= 0.55`
- `low`
  - anything else that still passed filters

### UI field meanings
Each suggested item returns:
- `product`
  - item name
- `suggested_qty`
  - recommended starting quantity
- `frequency`
  - how many times this exact route moved the product in the last 30 days
- `score`
  - internal strength number
- `confidence`
  - `high`, `medium`, or `low`
- `reason`
  - short explanation such as `frequently transferred recently`

### AI vs local logic
- recommendation scoring itself is local and deterministic
- the assistant layer may use Gemini for natural-language routing when available
- when Gemini is unavailable or quota-limited, the MCP server falls back to local routing

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
