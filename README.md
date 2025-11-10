# stockquery-mcp
Lightweight demo repo: FastAPI backend + an MCP-like tool server + local assistant client.

## What is included
- `src/main.py` : FastAPI backend service (inventory endpoints)
- `src/db.py` : SQLite mock DB and helper functions
- `src/mcp_server.py` : Lightweight MCP-style server that proxies tools
- `src/assistant_client.py` : Local chat client that uses OpenAI to decide on tool calls
- `.well-known/mcp.json` : discovery file for MCP-like tooling
- `requirements.txt` : Python dependencies

## Quickstart
1. Create & activate virtualenv:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Start backend:
   ```bash
   uvicorn src.main:app --reload --port 8000
   ```
3. Start MCP tool server (in another terminal):
   ```bash
   uvicorn src.mcp_server:app --reload --port 3000
   ```
4. (Optional) Run assistant client:
   ```bash
   export OPENAI_API_KEY='sk-...'
   python src/assistant_client.py
   ```

## Notes
- This is a learning/demo project. For production you should add authentication, TLS, proper error handling and tests.
- The assistant client expects the model to output a JSON object indicating tool calls; model behavior may vary. You can also bypass the model and call the tool endpoints directly.
