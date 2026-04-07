# Stock Assistant Backend Context

## Purpose
This repo powers the backend side of the Stock Assistant POC:
- FastAPI APIs for stock and transfer workflows
- local SQLite seed data
- MCP-style assistant server for natural-language interaction

This is intentionally lightweight. The goal is to demonstrate capability, not to build a production architecture.

## System Overview
- `src/main.py`
  FastAPI app exposing stock, product, store, and transfer recommendation endpoints.
- `src/db.py`
  Local SQLite setup, seed data, stock operations, and transfer recommendation logic.
- `src/mcp_server.py`
  Assistant-facing server. Handles natural language, tool routing, and concise replies.
- `src/schemas.py`
  Response/request models.

## Recommendation Logic
Recommendations are currently local and deterministic, not LLM-generated.

High-level flow:
- look at recent transfer history for a `from_store -> to_store -> transfer_type`
- use a 30-day cutoff
- group by product
- require at least 3 matching transfers
- score using:
  - frequency
  - recency
  - light quantity consistency
- ensure source stock can spare quantity beyond reorder level
- return:
  - `product`
  - `suggested_qty`
  - `frequency`
  - `score`
  - `confidence`
  - `reason`

## Assistant Behavior
- AI/natural-language layer should guide and explain, not invent source-of-truth transfer decisions.
- Recommendation requests should usually stay in chat and return concise summaries.
- Explicit transfer/open intents may return structured context to open Transfer Assist.
- New-colleague/onboarding questions should get short guidance replies.

## Seed Data
- Database is seeded on startup through `init_db()`.
- `src/store.db` is generated locally and should not be tracked.
- Main demo flows currently center on:
  - Parent Store `101`
  - PFS `201` and `204`
  - Staff Canteen `301`

## Example Prompts Supported
- `What can you do?`
- `How does Transfer Assist work?`
- `Suggest products for PFS 204`
- `What should I transfer to staff canteen?`
- `Show low stock in store 103`
- `Where is Milk 1L?`
- `Open transfer assist for canteen`

## Local Run Commands
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
uvicorn src.mcp_server:app --host 0.0.0.0 --port 3000 --reload
```

## Git Hygiene
- Do not commit local databases or IDE files.
- Do not commit local verification scratch scripts unless they are intentionally productized.
- Keep prompt behavior concise because mobile UI space is limited.
