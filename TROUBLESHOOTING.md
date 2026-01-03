# Troubleshooting

## Connection Refused (Android App)

### Symptoms
App crashes on launch with:
`java.net.ConnectException: Connection refused`

### Cause
1.  **Port Mismatch**: The Android app was configured to use port `3100` (`NetworkModule.kt`), but the MCP server runs on port `3000`.
2.  **Missing Endpoints**: The Android app tries to call `/tool/get_low_stock` and `/tool/transfer_stock`, which were missing from `mcp_server.py`.
3.  **Local IP Access**: When running on a physical device, the app must connect to the computer's LAN IP (e.g., `192.168.1.13`) instead of `localhost`.

### Resolution
1.  **Backend**:
    - Added `/tool/get_low_stock` and `/tool/transfer_stock` endpoints to `src/mcp_server.py`.
    - Fixed `db` import to `src.db` in `mcp_server.py`.
    - **Run Command**: Ensure servers are run with `--host 0.0.0.0` to allow external access:
      ```bash
      uvicorn src.mcp_server:app --reload --port 3000 --host 0.0.0.0
      ```

2.  **Android**:
    - Updated `BASE_URL` in `NetworkModule.kt` to use port `3000`.
    - ensured IP is set to the correct LAN IP (e.g., `192.168.1.13`).
