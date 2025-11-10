# assistant_client.py – streamlined test chat for MCP tools
import os, re, json, requests
from openai import OpenAI

MCP_TOOL_URL = "http://localhost:3100"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ Please set OPENAI_API_KEY in your environment")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are a helpful retail stock assistant.

If the user asks for stock info, output JSON ONLY in this format:
{"tool":"get_low_stock","args":{"store_id":103,"threshold":10}}

If the user asks to transfer stock, output:
{"tool":"transfer_stock","args":{"product_name":"Bread","from_store":101,"to_store":103,"quantity":5}}

Otherwise, respond normally in natural language.
"""

def call_model(prompt: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=400,
    )
    return resp.choices[0].message.content

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
        followup = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for a store inventory system."},
                {"role": "user", "content": f"Summarize this response in a short sentence: {tool_result}"},
            ],
            max_tokens=100,
        )
        print("Assistant:", followup.choices[0].message.content.strip())

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
