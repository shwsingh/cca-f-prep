
## W1D1 — API Basics
❌ Hardcoding API key in source code
   Fix: always load from .env using python-dotenv

❌ Not checking stop_reason on every response
   Fix: check response.stop_reason before processing — max_tokens is silent truncation
