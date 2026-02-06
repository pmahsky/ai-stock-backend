# assistant_client.py – streamlined test chat for MCP tools
import os, re, json, requests
import google.generativeai as genai

MCP_TOOL_URL = "http://localhost:3100"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("❌ Please set GEMINI_API_KEY in your environment")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

SYSTEM_PROMPT = """
You are a helpful retail stock assistant.

If the user asks for stock info, output JSON ONLY in this format:
{"tool":"get_low_stock","args":{"store_id":103,"threshold":10}}

If the user asks to transfer stock, output:
{"tool":"transfer_stock","args":{"product_name":"Bread","from_store":101,"to_store":103,"quantity":5}}

Otherwise, respond normally in natural language.
"""

def call_model(prompt: str) -> str:
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser: {prompt}"
    try:
        resp = model.generate_content(
            full_prompt,
            generation_config={"response_mime_type": "application/json"} 
            # Note: We enforce JSON because the system prompt asks for it, 
            # and it makes parsing easier for this script's logic.
        )
        return resp.text
    except Exception as e:
        return f"Error: {e}"

def invoke_tool(obj: dict):
    tool = obj.get("tool")
    args = obj.get("args", {})

    try:
        if tool == "get_low_stock":
            r = requests.get(f"{MCP_TOOL_URL}/tool/get_low_stock", params=args, timeout=10)
        elif tool == "transfer_stock":
            r = requests.post(f"{MCP_TOOL_URL}/tool/transfer_stock", json=args, timeout=10)
        else:
            print("Unknown tool:", tool)
            return

        r.raise_for_status()
        tool_result = r.json()
        print(f"Tool Response: {json.dumps(tool_result, indent=2)}")

        # Ask model for friendly rephrase
        followup = model.generate_content(
            f"You are a helpful assistant. Summarize this response in a short sentence: {tool_result}"
        )
        print("Assistant:", followup.text.strip())

    except requests.RequestException as e:
        print("❌ Tool call failed:", e)

def parse_json_from_text(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

def main():
    print("💬 Local Assistant (type 'exit' to quit)")
    while True:
        user = input("You: ").strip()
        if user.lower() in ("exit", "quit"):
            break

        model_out = call_model(user)
        print("Model:", model_out)

        parsed = parse_json_from_text(model_out)
        if parsed:
            print("Detected tool call ->", parsed)
            invoke_tool(parsed)
        else:
            print("Assistant:", model_out)

if __name__ == "__main__":
    main()
