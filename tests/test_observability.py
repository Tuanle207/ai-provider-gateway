import json

from ai_web_provider.core.errors import GenerationTimeoutError, QuotaExceededError, TaskFailedError
from ai_web_provider.core.models import AttemptRecord
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_provider_gateway.api.app import _provider_failure
from ai_provider_gateway.observability import RequestIdMiddleware, current_request_id, resolve_request_id


def _client(error: Exception | None = None) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/echo")
    async def echo():
        return {"request_id": current_request_id()}

    @app.get("/fail")
    async def fail():
        assert error is not None
        return _provider_failure("test_failed", error, "Image generation failed.")

    return TestClient(app)


def test_resolve_request_id_accepts_safe_ids_and_replaces_unsafe_ones() -> None:
    assert resolve_request_id("abc_DEF-123") == "abc_DEF-123"
    assert resolve_request_id(None).startswith("req_")
    assert resolve_request_id("bad id\n").startswith("req_")
    assert resolve_request_id("x" * 65).startswith("req_")


def test_middleware_round_trips_incoming_request_id() -> None:
    response = _client().get("/echo", headers={"X-Request-ID": "client-42"})
    assert response.headers["x-request-id"] == "client-42"
    assert response.json() == {"request_id": "client-42"}


def test_middleware_generates_request_id_when_missing() -> None:
    response = _client().get("/echo")
    request_id = response.headers["x-request-id"]
    assert request_id.startswith("req_")
    assert response.json() == {"request_id": request_id}


def _task_failed(error: Exception) -> TaskFailedError:
    attempt = AttemptRecord(attempt=1, account_email="a@example.com", ok=False, error_code="timeout", capture_id="101010_client-1_a1")
    failed = TaskFailedError(request_id="client-1", attempts=[attempt], last_error=error)
    failed.__cause__ = error
    return failed


def test_provider_failure_maps_timeout_and_includes_request_id() -> None:
    response = _client(_task_failed(GenerationTimeoutError("did not complete within 360s"))).get(
        "/fail", headers={"X-Request-ID": "client-1"}
    )
    assert response.status_code == 504
    assert response.headers["x-request-id"] == "client-1"
    assert response.json() == {
        "error": {
            "message": "The provider did not finish in time.",
            "type": "server_error",
            "code": "provider_timeout",
            "request_id": "client-1",
        }
    }
    # Internal details (paths, capture ids, raw error text) never reach the client.
    assert "360s" not in json.dumps(response.json())
    assert "101010" not in json.dumps(response.json())


def test_provider_failure_maps_quota_to_429() -> None:
    response = _client(_task_failed(QuotaExceededError("out of credits"))).get("/fail")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "provider_quota_exceeded"
    assert response.json()["error"]["type"] == "rate_limit_error"


def test_provider_failure_unknown_error_is_502() -> None:
    response = _client(RuntimeError("boom")).get("/fail")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"
    assert response.json()["error"]["message"] == "Image generation failed."
