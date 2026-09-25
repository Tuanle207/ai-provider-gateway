import hmac
import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ai_provider_gateway.application.chat_completions import ChatCompletions
from ai_provider_gateway.config import Settings, settings
from ai_provider_gateway.infrastructure.conversation_store import ConversationStore
from ai_provider_gateway.integrations.perplexity.adapter import PerplexityTextToTextAdapter
from ai_provider_gateway.integrations.registry import known_model_ids, list_models, resolve_model
from ai_provider_gateway.version import __version__

_settings: Settings | None = None
_store: ConversationStore | None = None
_service: ChatCompletions | None = None


def _configured() -> tuple[Settings, ChatCompletions]:
    if _settings is None or _service is None:
        raise RuntimeError("Application has not started.")
    return _settings, _service


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _settings, _store, _service
    _settings = settings(known_model_ids())
    _store = ConversationStore(_settings.state_dir)
    _service = ChatCompletions(PerplexityTextToTextAdapter(_settings.state_dir, _settings.perplexity_cookies), _store)
    yield
    await _store.close()
    _settings = None
    _store = None
    _service = None


app = FastAPI(title="AI Provider Gateway", version=__version__, lifespan=lifespan)


def _error(status: int, message: str, param: str | None = None, code: str | None = None) -> JSONResponse:
    error: dict[str, Any] = {"message": message, "type": "invalid_request_error"}
    if param:
        error["param"] = param
    if code:
        error["code"] = code
    return JSONResponse(status_code=status, content={"error": error})


def _content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(str(item.get("text", "")) for item in value if isinstance(item, dict))
    return ""


def _authorized(request: Request) -> bool:
    configured, _ = _configured()
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return scheme.lower() == "bearer" and bool(token) and hmac.compare_digest(token, configured.api_key)


def _authentication_error() -> JSONResponse:
    response = _error(401, "Incorrect API key provided.", code="invalid_api_key")
    response.headers["WWW-Authenticate"] = "Bearer"
    return response


def _completion(model: str, text: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": re.sub(r"\[\d+\]", "", text)}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _sse(messages: list[dict], model_id: str, model, conversation_id: str | None):
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def event(delta: dict[str, str], finish_reason: str | None = None) -> str:
        payload = {"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model_id, "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}
        return f"data: {json.dumps(payload)}\n\n"

    yield event({"role": "assistant"})
    _, service = _configured()
    async for result in service.stream(messages, model, conversation_id):
        if result.text:
            yield event({"content": re.sub(r"\[\d+\]", "", result.text)})
    yield event({}, "stop")
    yield "data: [DONE]\n\n"


@app.get("/v1/models")
async def models(request: Request):
    if not _authorized(request):
        return _authentication_error()
    configured, _ = _configured()
    return {"object": "list", "data": [{"id": model.id, "object": "model", "created": 0, "owned_by": model.provider} for model in list_models(configured.available_models)]}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    if not _authorized(request):
        return _authentication_error()
    configured, service = _configured()
    try:
        body = await request.json()
    except Exception:
        return _error(400, "Malformed JSON body", "request")
    if not isinstance(body, dict):
        return _error(400, "Body must be a JSON object", "request")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return _error(400, "`messages` must be a non-empty array", "messages")
    if not all(isinstance(message, dict) and _content(message.get("content")) for message in messages):
        return _error(400, "Each message must contain text content", "messages")
    model_id = body.get("model")
    model = resolve_model(model_id, configured.default_model, configured.available_models)
    if model is None:
        return _error(404, f"The model `{model_id}` does not exist.", "model", "model_not_found")
    public_model_id = model.id
    conversation_id = request.headers.get("x-perplexity-conversation-id")
    if body.get("stream"):
        return StreamingResponse(_sse(messages, public_model_id, model, conversation_id), media_type="text/event-stream")
    try:
        result = await service.complete(messages, model, conversation_id)
    except Exception as error:
        return _error(502, str(error))
    return _completion(public_model_id, result.text)


def main() -> None:
    import uvicorn

    configured = settings(known_model_ids())
    uvicorn.run(app, host=configured.host, port=configured.port)
