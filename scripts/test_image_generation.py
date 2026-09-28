"""Call the OpenAI-compatible image-generation endpoint and save returned images."""

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# base_url = os.environ.get("AI_PROVIDER_GATEWAY_URL", "http://127.0.0.1:8002")
base_url = os.environ.get("AI_PROVIDER_GATEWAY_URL", "https://vcreator.wordphere.com/api/ai")
model = os.environ.get("AI_PROVIDER_GATEWAY_IMAGE_MODEL", "web-google-flow/nano-banana-2")
prompts = [
    "A boy playing in the park with a cat",
    "A robot painting a sunset over the ocean",
    "A cozy cabin in a snowy forest at night",
]
size = os.environ.get("AI_PROVIDER_GATEWAY_IMAGE_SIZE", "1376x768")
count = int(os.environ.get("AI_PROVIDER_GATEWAY_IMAGE_COUNT", "1"))
response_format = os.environ.get("AI_PROVIDER_GATEWAY_IMAGE_RESPONSE_FORMAT", "b64_json")
api_key = os.environ.get("AI_PROVIDER_GATEWAY_API_KEY", "test-token")
output_dir = Path(os.environ.get("AI_PROVIDER_GATEWAY_IMAGE_OUTPUT_DIR", "generated-images"))

if not api_key:
    raise SystemExit("AI_PROVIDER_GATEWAY_API_KEY must be set.")

if response_format not in {"url", "b64_json"}:
    raise SystemExit("AI_PROVIDER_GATEWAY_IMAGE_RESPONSE_FORMAT must be `url` or `b64_json`.")


def generate_images(prompt: str, prompt_index: int) -> None:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "n": count,
            "size": size,
            "response_format": response_format,
        }
    ).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/v1/images/generations",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=300) as response:
            body = json.loads(response.read())
    except HTTPError as error:
        raise RuntimeError(f"Gateway returned HTTP {error.code}: {error.read().decode('utf-8')}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach gateway at {base_url}: {error.reason}") from error

    for image_index, image in enumerate(body["data"], start=1):
        if "url" in image:
            print(image["url"])
            continue
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"image-{prompt_index}-{image_index}.png"
        path.write_bytes(base64.b64decode(image["b64_json"]))
        print(path.resolve())


with ThreadPoolExecutor(max_workers=len(prompts)) as executor:
    futures = {
        executor.submit(generate_images, prompt, prompt_index): (prompt_index, prompt)
        for prompt_index, prompt in enumerate(prompts, start=1)
    }
    for future in as_completed(futures):
        prompt_index, prompt = futures[future]
        try:
            future.result()
        except RuntimeError as error:
            print(f"Prompt {prompt_index} ({prompt!r}) failed: {error}")
