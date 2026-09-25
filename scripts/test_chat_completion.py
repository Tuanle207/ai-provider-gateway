"""Call the local OpenAI-compatible chat-completions endpoint."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


base_url = os.environ.get("AI_PROVIDER_GATEWAY_URL", "http://127.0.0.1:8001")
model = os.environ.get("AI_PROVIDER_GATEWAY_MODEL", "perplexity/claude-sonnet-5")
prompt = os.environ.get("AI_PROVIDER_GATEWAY_PROMPT", "What is the capital of France?")

payload = json.dumps(
    {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
).encode("utf-8")
request = Request(
    f"{base_url.rstrip('/')}/v1/chat/completions",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urlopen(request, timeout=120) as response:
        body = json.loads(response.read())
except HTTPError as error:
    raise SystemExit(f"Gateway returned HTTP {error.code}: {error.read().decode('utf-8')}") from error
except URLError as error:
    raise SystemExit(f"Could not reach gateway at {base_url}: {error.reason}") from error

print(body["choices"][0]["message"]["content"])
