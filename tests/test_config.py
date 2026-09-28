import json

import pytest

from ai_provider_gateway.config import _load_google_flow_projects


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
