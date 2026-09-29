"""Request correlation and logging for the gateway.

Every HTTP request gets a request id (the caller's `X-Request-ID` when it is safe, otherwise a
generated one). It is bound into structlog's context so every log line — including those emitted
by ai-web-provider while the request runs — carries it, echoed back in the `X-Request-ID`
response header, passed to ai-web-provider tasks, and included in error bodies. Operators use it
to find the matching failure capture under `$STATE_DIR/web-automation/failures/`.
"""

import re
import time
import uuid

import structlog
from ai_web_provider.core.logging_setup import get_logger

REQUEST_ID_HEADER = "x-request-id"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_QUIET_PATHS = frozenset({"/health"})
_log = get_logger()


def resolve_request_id(incoming: str | None) -> str:
    if incoming and _VALID_REQUEST_ID.fullmatch(incoming):
        return incoming
    return f"req_{uuid.uuid4().hex}"


def current_request_id() -> str | None:
    value = structlog.contextvars.get_contextvars().get("request_id")
    return value if isinstance(value, str) else None


class RequestIdMiddleware:
    """Pure ASGI middleware (safe for streaming responses)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        request_id = resolve_request_id(headers.get(REQUEST_ID_HEADER))
        started = time.monotonic()
        status: dict[str, int] = {}

        async def send_with_request_id(message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [
                    *(item for item in message["headers"] if item[0].lower() != REQUEST_ID_HEADER.encode()),
                    (REQUEST_ID_HEADER.encode(), request_id.encode()),
                ]
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                await self.app(scope, receive, send_with_request_id)
            finally:
                if scope.get("path") not in _QUIET_PATHS:
                    _log.info(
                        "http_request",
                        method=scope.get("method"),
                        path=scope.get("path"),
                        status=status.get("code"),
                        duration_ms=round((time.monotonic() - started) * 1000),
                    )
