import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str
    host: str
    port: int
    state_dir: Path
    public_base_url: str | None
    web_automation_headless: bool
    web_automation_max_concurrent_jobs: int
    web_automation_per_account_concurrency: int
    web_automation_default_timeout_seconds: float
    web_automation_max_retries: int
    web_automation_cooldown_minutes: float
    web_provider_settings: dict[str, dict[str, Any]]
    chat_default_model: str
    chat_available_models: tuple[str, ...]
    image_default_model: str | None
    image_available_models: tuple[str, ...]
    perplexity_cookies: str | None

    @property
    def text_default_model(self) -> str:
        return self.chat_default_model

    @property
    def text_available_models(self) -> tuple[str, ...]:
        return self.chat_available_models


def settings(known_models: tuple[str, ...]) -> Settings:
    api_key = os.environ.get("AI_PROVIDER_GATEWAY_API_KEY", "")
    chat_known_models = tuple(model for model in known_models if model.startswith("perplexity/") or model.startswith("web-perplexity/"))
    image_known_models = tuple(model for model in known_models if model.startswith("web-google-flow/"))
    chat_value = os.environ.get("CHAT_AVAILABLE_MODELS", os.environ.get("TEXT_AVAILABLE_MODELS"))
    chat_available_models = tuple(model.strip() for model in chat_value.split(",") if model.strip()) if chat_value else chat_known_models
    chat_default_model = os.environ.get("CHAT_DEFAULT_MODEL", os.environ.get("TEXT_DEFAULT_MODEL", "perplexity/sonar-2"))
    image_value = os.environ.get("IMAGE_AVAILABLE_MODELS")
    image_available_models = tuple(model.strip() for model in image_value.split(",") if model.strip()) if image_value else ()
    image_default_model = os.environ.get("IMAGE_DEFAULT_MODEL")
    public_base_url = os.environ.get("AI_PROVIDER_GATEWAY_PUBLIC_BASE_URL")
    unknown = set(chat_available_models + image_available_models) - set(known_models)
    wrong_chat_capability = set(chat_available_models) - set(chat_known_models)
    wrong_image_capability = set(image_available_models) - set(image_known_models)

    if not api_key:
        raise RuntimeError("AI_PROVIDER_GATEWAY_API_KEY must be set.")
    if not chat_available_models:
        raise RuntimeError("CHAT_AVAILABLE_MODELS must contain at least one model.")
    if unknown:
        raise RuntimeError(f"Configured model allowlists contain unknown model(s): {', '.join(sorted(unknown))}")
    if wrong_chat_capability:
        raise RuntimeError(f"CHAT_AVAILABLE_MODELS contains non-chat model(s): {', '.join(sorted(wrong_chat_capability))}")
    if wrong_image_capability:
        raise RuntimeError(f"IMAGE_AVAILABLE_MODELS contains non-image model(s): {', '.join(sorted(wrong_image_capability))}")
    if chat_default_model not in chat_available_models:
        raise RuntimeError("CHAT_DEFAULT_MODEL must be included in CHAT_AVAILABLE_MODELS.")
    if image_default_model and image_default_model not in image_available_models:
        raise RuntimeError("IMAGE_DEFAULT_MODEL must be included in IMAGE_AVAILABLE_MODELS.")
    if public_base_url and not public_base_url.startswith(("http://", "https://")):
        raise RuntimeError("AI_PROVIDER_GATEWAY_PUBLIC_BASE_URL must be an absolute HTTP(S) URL.")
    web_provider_settings: dict[str, dict[str, Any]] = {"perplexity": {}, "google_flow": {}}
    for environment_name, value in os.environ.items():
        for provider, prefix in (("perplexity", "WEB_PERPLEXITY_"), ("google_flow", "WEB_GOOGLE_FLOW_")):
            if environment_name.startswith(prefix) and environment_name != "WEB_GOOGLE_FLOW_PROJECTS_FILE":
                web_provider_settings[provider][environment_name[len(prefix):].lower()] = value

    projects_file = os.environ.get("WEB_GOOGLE_FLOW_PROJECTS_FILE")
    if projects_file:
        web_provider_settings["google_flow"]["projects_by_account"] = _load_google_flow_projects(
            Path(projects_file)
        )
    elif image_available_models:
        raise RuntimeError("WEB_GOOGLE_FLOW_PROJECTS_FILE must be set when image models are enabled.")
    configured_concurrency = web_provider_settings["google_flow"].get(
        "per_account_concurrency", os.environ.get("WEB_AUTOMATION_PER_ACCOUNT_CONCURRENCY", "1")
    )
    if projects_file:
        try:
            required_projects = int(configured_concurrency)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("WEB_GOOGLE_FLOW_PER_ACCOUNT_CONCURRENCY must be an integer.") from exc
        if required_projects < 1:
            raise RuntimeError("WEB_GOOGLE_FLOW_PER_ACCOUNT_CONCURRENCY must be at least one.")
        for email, projects in web_provider_settings["google_flow"]["projects_by_account"].items():
            if len(projects) < required_projects:
                raise RuntimeError(
                    f"Google Flow account {email!r} has {len(projects)} project(s), but requires "
                    f"{required_projects} for its configured concurrency."
                )

    return Settings(
        api_key=api_key,
        host=os.environ.get("OPENAI_HOST", "127.0.0.1"),
        port=int(os.environ.get("OPENAI_PORT", "8002")),
        state_dir=Path(os.environ.get("AI_PROVIDER_GATEWAY_STATE_DIR", Path.home() / ".local" / "state" / "ai-provider-gateway")),
        public_base_url=public_base_url.rstrip("/") if public_base_url else None,
        web_automation_headless=os.environ.get("WEB_AUTOMATION_HEADLESS", "true").lower() not in {"0", "false", "no"},
        web_automation_max_concurrent_jobs=int(os.environ.get("WEB_AUTOMATION_MAX_CONCURRENT_JOBS", "4")),
        web_automation_per_account_concurrency=int(os.environ.get("WEB_AUTOMATION_PER_ACCOUNT_CONCURRENCY", "1")),
        web_automation_default_timeout_seconds=float(os.environ.get("WEB_AUTOMATION_DEFAULT_TIMEOUT_SECONDS", "180")),
        web_automation_max_retries=int(os.environ.get("WEB_AUTOMATION_MAX_RETRIES", "3")),
        web_automation_cooldown_minutes=float(os.environ.get("WEB_AUTOMATION_COOLDOWN_MINUTES", "5")),
        web_provider_settings=web_provider_settings,
        chat_default_model=chat_default_model,
        chat_available_models=chat_available_models,
        image_default_model=image_default_model,
        image_available_models=image_available_models,
        perplexity_cookies=os.environ.get("PERPLEXITY_COOKIES"),
    )


def _load_google_flow_projects(path: Path) -> dict[str, list[str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Could not read WEB_GOOGLE_FLOW_PROJECTS_FILE {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"WEB_GOOGLE_FLOW_PROJECTS_FILE {path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("accounts"), dict):
        raise RuntimeError("WEB_GOOGLE_FLOW_PROJECTS_FILE must contain version 1 and an accounts object.")

    projects_by_account: dict[str, list[str]] = {}
    assigned_projects: set[str] = set()
    for email, account_config in raw["accounts"].items():
        if not isinstance(email, str) or "@" not in email:
            raise RuntimeError("Google Flow project configuration contains an invalid account email.")
        if not isinstance(account_config, dict) or not isinstance(account_config.get("projects"), list):
            raise RuntimeError(f"Google Flow account {email!r} must define a projects array.")
        normalized_email = email.strip().lower()
        projects = account_config["projects"]
        if not projects or not all(isinstance(project, str) and project.strip() for project in projects):
            raise RuntimeError(f"Google Flow account {normalized_email!r} must define non-empty project IDs.")
        normalized_projects = [project.strip() for project in projects]
        if len(set(normalized_projects)) != len(normalized_projects):
            raise RuntimeError(f"Google Flow account {normalized_email!r} contains duplicate project IDs.")
        duplicate = assigned_projects.intersection(normalized_projects)
        if duplicate:
            raise RuntimeError(f"Google Flow project IDs cannot be assigned to multiple accounts: {sorted(duplicate)!r}")
        assigned_projects.update(normalized_projects)
        projects_by_account[normalized_email] = normalized_projects
    if not projects_by_account:
        raise RuntimeError("WEB_GOOGLE_FLOW_PROJECTS_FILE must configure at least one account.")
    return projects_by_account
