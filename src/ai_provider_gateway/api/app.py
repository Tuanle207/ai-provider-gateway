import base64
import hmac
import json
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from ai_provider_gateway.application.chat_completions import ChatCompletions
from ai_provider_gateway.application.image_generations import ImageGenerations
from ai_provider_gateway.config import Settings, settings
from ai_provider_gateway.domain.image_generation import ImageGenerationRequest
from ai_provider_gateway.infrastructure.artifact_store import ArtifactStore
from ai_provider_gateway.infrastructure.conversation_store import ConversationStore
from ai_provider_gateway.integrations.perplexity.adapter import PerplexityTextToTextAdapter
from ai_provider_gateway.integrations.web_google_flow.adapter import WebGoogleFlowImageAdapter
from ai_provider_gateway.integrations.web_perplexity.adapter import WebPerplexityTextToTextAdapter
from ai_provider_gateway.integrations.web_runtime.runtime import WebProviderRuntime
from ai_provider_gateway.integrations.registry import known_model_ids, list_models, resolve_chat_model, resolve_image_model
from ai_provider_gateway.version import __version__

_settings: Settings | None = None
_store: ConversationStore | None = None
_service: ChatCompletions | None = None
_image_service: ImageGenerations | None = None
_artifacts: ArtifactStore | None = None
_web_runtime: WebProviderRuntime | None = None


def _configured() -> tuple[Settings, ChatCompletions, ImageGenerations, ArtifactStore]:
    if _settings is None or _service is None or _image_service is None or _artifacts is None:
        raise RuntimeError("Application has not started.")
    return _settings, _service, _image_service, _artifacts


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _settings, _store, _service, _image_service, _artifacts, _web_runtime
    _settings = settings(known_model_ids())
    _web_runtime = WebProviderRuntime(
        _settings.state_dir,
        headless=_settings.web_automation_headless,
        max_concurrent_browsers=_settings.web_automation_max_concurrent_browsers,
        per_account_concurrency=_settings.web_automation_per_account_concurrency,
        default_timeout_seconds=_settings.web_automation_default_timeout_seconds,
        max_retries=_settings.web_automation_max_retries,
        cooldown_minutes=_settings.web_automation_cooldown_minutes,
        provider_settings=_settings.web_provider_settings,
    )
    await _web_runtime.startup()
    _store = ConversationStore(_settings.state_dir)
    _service = ChatCompletions({
        "perplexity": PerplexityTextToTextAdapter(_settings.state_dir, _settings.perplexity_cookies),
        "web-perplexity": WebPerplexityTextToTextAdapter(_web_runtime, _settings.web_automation_default_timeout_seconds),
    }, _store)
    _image_service = ImageGenerations({"web-google-flow": WebGoogleFlowImageAdapter(_web_runtime, _settings.web_automation_default_timeout_seconds)})
    _artifacts = ArtifactStore(_web_runtime.output_dir)
    yield
    await _store.close()
    await _web_runtime.shutdown()
    _settings = None
    _store = None
    _service = None
    _image_service = None
    _artifacts = None
    _web_runtime = None


app = FastAPI(title="AI Provider Gateway", version=__version__, lifespan=lifespan)


def _error(status: int, message: str, param: str | None = None, code: str | None = None) -> JSONResponse:
    error: dict[str, Any] = {"message": message, "type": "invalid_request_error"}
    if param:
        error["param"] = param
    if code:
        error["code"] = code
    return JSONResponse(status_code=status, content={"error": error})


def _valid_message(message: Any) -> bool:
    if not isinstance(message, dict) or message.get("tool_calls"):
        return False
    content = message.get("content")
    if isinstance(content, str):
        return bool(content)
    if not isinstance(content, list) or not content:
        return False
    return all(isinstance(item, dict) and item.get("type", "text") == "text" and isinstance(item.get("text"), str) and item["text"] for item in content)


def _authorized(request: Request) -> bool:
    configured, _, _, _ = _configured()
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return scheme.lower() == "bearer" and bool(token) and hmac.compare_digest(token, configured.api_key)


def _authentication_error() -> JSONResponse:
    response = _error(401, "Incorrect API key provided.", code="invalid_api_key")
    response.headers["WWW-Authenticate"] = "Bearer"
    return response


def _completion(model: str, text: str) -> dict[str, Any]:
    return {"id": f"chatcmpl-{uuid.uuid4().hex}", "object": "chat.completion", "created": int(time.time()), "model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": re.sub(r"\[\d+\]", "", text)}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}


async def _sse(messages: list[dict], model_id: str, model, conversation_id: str | None):
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def event(delta: dict[str, str], finish_reason: str | None = None) -> str:
        payload = {"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model_id, "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}
        return f"data: {json.dumps(payload)}\n\n"

    yield event({"role": "assistant"})
    _, service, _, _ = _configured()
    async for result in service.stream(messages, model, conversation_id):
        if result.text:
            yield event({"content": re.sub(r"\[\d+\]", "", result.text)})
    yield event({}, "stop")
    yield "data: [DONE]\n\n"


@app.get("/v1/models")
async def models(request: Request):
    if not _authorized(request):
        return _authentication_error()
    configured, _, _, _ = _configured()
    available_models = configured.chat_available_models + configured.image_available_models
    return {"object": "list", "data": [{"id": model.id, "object": "model", "created": 0, "owned_by": model.provider} for model in list_models(available_models)]}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    if not _authorized(request):
        return _authentication_error()
    configured, service, _, _ = _configured()
    try:
        body = await request.json()
    except Exception:
        return _error(400, "Malformed JSON body", "request")
    if not isinstance(body, dict):
        return _error(400, "Body must be a JSON object", "request")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return _error(400, "`messages` must be a non-empty array", "messages")
    if not all(_valid_message(message) for message in messages):
        return _error(400, "Only non-empty text message content is supported", "messages")
    model_id = body.get("model")
    model = resolve_chat_model(model_id, configured.chat_default_model, configured.chat_available_models)
    if model is None:
        return _error(404, f"The model `{model_id}` does not exist.", "model", "model_not_found")
    conversation_id = request.headers.get("x-conversation-id")
    if body.get("stream"):
        return StreamingResponse(_sse(messages, model.id, model, conversation_id), media_type="text/event-stream")
    try:
        result = await service.complete(messages, model, conversation_id)
    except Exception as error:
        return _error(502, str(error))
    return _completion(model.id, result.text)


@app.post("/v1/images/generations")
async def image_generations(request: Request):
    if not _authorized(request):
        return _authentication_error()
    configured, _, service, artifacts = _configured()
    try:
        body = await request.json()
    except Exception:
        return _error(400, "Malformed JSON body", "request")
    if not isinstance(body, dict):
        return _error(400, "Body must be a JSON object", "request")
    unsupported = set(body) - {"model", "prompt", "n", "size", "response_format"}
    if unsupported:
        return _error(400, f"Unsupported image request field(s): {', '.join(sorted(unsupported))}", "request")
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return _error(400, "`prompt` must be a non-empty string", "prompt")
    n = body.get("n", 1)
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 4:
        return _error(400, "`n` must be an integer from 1 through 4", "n")
    aspect_ratios = {"1024x1024": "1:1", "768x1024": "3:4", "1024x768": "4:3", "768x1376": "9:16", "1376x768": "16:9"}
    size = body.get("size", "1024x1024")
    if size not in aspect_ratios:
        return _error(400, "Unsupported `size`", "size")
    response_format = body.get("response_format", "url")
    if response_format not in {"url", "b64_json"}:
        return _error(400, "`response_format` must be `url` or `b64_json`", "response_format")
    if response_format == "url" and not configured.public_base_url:
        return _error(400, "AI_PROVIDER_GATEWAY_PUBLIC_BASE_URL is required for URL responses", "response_format")
    model_id = body.get("model")
    model = resolve_image_model(model_id, configured.image_default_model or "", configured.image_available_models)
    if model is None:
        return _error(404, f"The image model `{model_id}` does not exist.", "model", "model_not_found")
    try:
        images = await service.generate(ImageGenerationRequest(prompt, n, aspect_ratios[size], model))
        if len(images) != n:
            raise RuntimeError("Provider returned an incomplete image generation result.")
        data = []
        for image in images:
            artifact = artifacts.register(image.path, image.mime_type)
            data.append({"b64_json": base64.b64encode(artifact.path.read_bytes()).decode("ascii")} if response_format == "b64_json" else {"url": f"{configured.public_base_url}/v1/artifacts/{artifact.id}"})
    except LookupError:
        return _error(503, "The image provider is not available.", code="service_unavailable")
    except Exception:
        return _error(502, "Image generation failed.", code="provider_error")
    return {"created": int(time.time()), "data": data}


@app.get("/v1/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, request: Request):
    if not _authorized(request):
        return _authentication_error()
    _, _, _, artifacts = _configured()
    artifact = artifacts.get(artifact_id)
    if artifact is None:
        return _error(404, "Artifact not found.", "artifact_id", "artifact_not_found")
    return FileResponse(artifact.path, media_type=artifact.mime_type)


def main() -> None:
    import uvicorn

    configured = settings(known_model_ids())
    uvicorn.run(app, host=configured.host, port=configured.port)
