import os
from dotenv import load_dotenv
import anthropic

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key or "PASTE" in api_key:
    print("❌ ANTHROPIC_API_KEY not set in .env")
    print("   Get your key at: console.anthropic.com/settings/keys")
    print("   Then: nano ~/Documents/cca-f-prep/.env")
    exit(1)

client = anthropic.Anthropic(api_key=api_key)
MODEL  = "claude-haiku-4-5"

print("\nMaking first API call...\n")
response = client.messages.create(
    model=MODEL,
    max_tokens=150,
    system="You are a helpful assistant for MeterFlow, a usage-based billing SaaS.",
    messages=[{"role":"user","content":"Say hello and confirm you are ready to help the MeterFlow support team. One sentence only."}]
)

print("✅ API connection OK\n")
print(f"Claude says:\n  {response.content[0].text}\n")
print("-"*50)
print("RAW RESPONSE FIELDS — memorize these:")
print(f"  stop_reason    : '{response.stop_reason}'")
print(f"  model          : '{response.model}'")
print(f"  input_tokens   : {response.usage.input_tokens}")
print(f"  output_tokens  : {response.usage.output_tokens}")
print(f"  content[0].type: '{response.content[0].type}'")

print("\n" + "-"*50)
print("TEST: max_tokens=10 — what happens when truncated?\n")
r2 = client.messages.create(
    model=MODEL, max_tokens=10,
    messages=[{"role":"user","content":"Write a 3-sentence welcome message for MeterFlow customers."}]
)
print(f"  stop_reason  : '{r2.stop_reason}'")
print(f"  output_tokens: {r2.usage.output_tokens}")
print(f"  text         : '{r2.content[0].text}'")
if r2.stop_reason == "max_tokens":
    print("\n⚠️  TRUNCATED — stop_reason is max_tokens not end_turn")
    print("   In an agent loop you MUST check stop_reason on every response.")

print("\n" + "-"*50)
print("TEST: multi-turn conversation — preview of Day 4\n")
messages = []
for user_text in [
    "Hi, I'm account A-1042. I was charged twice in May.",
    "How long does a refund take?"
]:
    messages.append({"role":"user","content":user_text})
    r3 = client.messages.create(model=MODEL, max_tokens=80,
        system="You are a MeterFlow billing support agent. Keep replies to 1 sentence.",
        messages=messages)
    messages.append({"role":"assistant","content":r3.content[0].text})
    print(f"  User   : {user_text}")
    print(f"  Claude : {r3.content[0].text}\n")

print("-"*50)
print("Day 1 complete. Run:")
print("  bash scripts/end_day.sh 'W1D1: setup — API call, stop_reason, multi-turn'")
print("  git push")

os.makedirs("notes", exist_ok=True)
with open("notes/anti-patterns.md", "a") as f:
    f.write("\n## W1D1 — API Basics\n")
    f.write("❌ Hardcoding API key in source code\n")
    f.write("   Fix: always load from .env using python-dotenv\n\n")
    f.write("❌ Not checking stop_reason on every response\n")
    f.write("   Fix: check response.stop_reason before processing — max_tokens is silent truncation\n")
print("\n✅ notes/anti-patterns.md updated")
