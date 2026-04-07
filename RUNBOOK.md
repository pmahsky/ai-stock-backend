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
