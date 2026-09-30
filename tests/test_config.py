import json

import pytest

from ai_provider_gateway.config import _load_google_flow_projects, settings


def _browser_executable(tmp_path):
    executable = tmp_path / "chrome"
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    return executable


def _configure_browser_test(monkeypatch, executable) -> None:
    monkeypatch.setenv("AI_PROVIDER_GATEWAY_API_KEY", "test")
    monkeypatch.setenv("CHAT_AVAILABLE_MODELS", "perplexity/sonar-2")
    monkeypatch.delenv("IMAGE_AVAILABLE_MODELS", raising=False)
    monkeypatch.delenv("IMAGE_DEFAULT_MODEL", raising=False)
    monkeypatch.setenv("WEB_AUTOMATION_UNGOOGLED_CHROMIUM_EXECUTABLE", str(executable))


def test_settings_reads_browser_configuration(monkeypatch, tmp_path) -> None:
    executable = _browser_executable(tmp_path)
    _configure_browser_test(monkeypatch, executable)
    monkeypatch.setenv("WEB_AUTOMATION_BROWSER_IDLE_TIMEOUT_SECONDS", "42")

    configured = settings(("perplexity/sonar-2",))

    assert configured.web_automation_ungoogled_chromium_executable == executable
    assert configured.web_automation_browser_idle_timeout_seconds == 42


def test_settings_rejects_invalid_browser_configuration(monkeypatch, tmp_path) -> None:
    _configure_browser_test(monkeypatch, tmp_path / "missing")

    with pytest.raises(RuntimeError, match="WEB_AUTOMATION_UNGOOGLED_CHROMIUM_EXECUTABLE"):
        settings(("perplexity/sonar-2",))


def test_settings_rejects_negative_browser_idle_timeout(monkeypatch, tmp_path) -> None:
    executable = _browser_executable(tmp_path)
    _configure_browser_test(monkeypatch, executable)
    monkeypatch.setenv("WEB_AUTOMATION_BROWSER_IDLE_TIMEOUT_SECONDS", "-1")

    with pytest.raises(RuntimeError, match="IDLE_TIMEOUT"):
        settings(("perplexity/sonar-2",))


def test_load_google_flow_projects_normalizes_accounts(tmp_path) -> None:
    path = tmp_path / "projects.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "accounts": {"Account@Example.Com": {"projects": ["project-a", "project-b"]}},
            }
        ),
        encoding="utf-8",
    )

    assert _load_google_flow_projects(path) == {
        "account@example.com": ["project-a", "project-b"]
    }


def test_load_google_flow_projects_rejects_duplicate_projects(tmp_path) -> None:
    path = tmp_path / "projects.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "accounts": {"account@example.com": {"projects": ["project-a", "project-a"]}},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="duplicate"):
        _load_google_flow_projects(path)
