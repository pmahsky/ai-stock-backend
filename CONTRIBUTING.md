# Contributing

## Working Style
- Treat this as a POC, not a production platform.
- Prefer simple, readable solutions over abstraction-heavy ones.
- Preserve the split:
  - local logic decides recommendation candidates
  - assistant layer explains and guides

## Before Editing
- read [AGENTS.md](/Users/prashantmahskey/Documents/StockAssistant/ai-stock-backend/AGENTS.md)
- check [RUNBOOK.md](/Users/prashantmahskey/Documents/StockAssistant/ai-stock-backend/RUNBOOK.md)
- confirm which repo you are in; Android and backend are separate git repos

## Backend Rules
- keep recommendation logic in `src/db.py` lightweight and explainable
- keep response models in `src/schemas.py`
- keep `src/main.py` thin
- keep `src/mcp_server.py` focused on chat routing and concise replies

## AI / Prompting Rules
- replies should be short and mobile-friendly
- recommendation questions should usually stay in chat
- only explicit open/transfer intents should hand off into Transfer Assist
- onboarding/help questions should get direct answers

## Data Rules
- `src/store.db` is generated locally and should not be committed
- local scratch DBs and helper scripts should stay out of git unless intentionally productized

## Verification
Run before handing off:
```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile src/db.py src/main.py src/mcp_server.py src/schemas.py
```

## Git Hygiene
- do not commit IDE files
- do not commit local databases
- do not commit temporary verification scripts unless they are part of the product
- keep README / AGENTS / RUNBOOK updated when workflow changes
