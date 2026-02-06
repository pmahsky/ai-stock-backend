# Changelog

## [Unreleased] - 2026-02-06

### Migrated
- **AI Provider**: Switched from OpenAI (gpt-4o-mini) to Google Gemini (gemini-2.0-flash-001) for improved performance and Pay-as-you-go billing support.

### Added
- **Contextual Awareness**:
  - Assistant now resolves implicit arguments from conversation history (e.g., "Is *it* low?").
  - Auto-correction for product typos in user queries.
- **Specific Stock Checks**:
  - `get_low_stock` tool now supports a `product` argument to return the status of a specific item (Low/OK) instead of just a general list.
  - New `/product_details` endpoint and `get_product_info` tool for detailed product queries.
- **Billing Optimization**:
  - Replaced expensive "AI naturalization" (rephrasing) step with robust Python templates to reduce API call volume by 50% and improve latency.

### Changed
- **Tool Logic**:
  - `run_tool` pipeline updated to handle new tool arguments and return template-based natural responses.
  - `BASE_SYSTEM_PROMPT` updated with explicit history usage rules and dynamic product list injection.
- **Dependencies**:
  - Replaced `openai` with `google-generativeai` in `requirements.txt`.
