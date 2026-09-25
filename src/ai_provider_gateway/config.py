import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_key: str
    host: str
    port: int
    state_dir: Path
    default_model: str
    available_models: tuple[str, ...]
    perplexity_cookies: str | None


def settings(known_models: tuple[str, ...]) -> Settings:
    api_key = os.environ.get("AI_PROVIDER_GATEWAY_API_KEY", "")
    available_value = os.environ.get("TEXT_AVAILABLE_MODELS")
    available_models = tuple(model.strip() for model in available_value.split(",") if model.strip()) if available_value else known_models
    default_model = os.environ.get("TEXT_DEFAULT_MODEL", "perplexity/sonar-2")
    unknown = set(available_models) - set(known_models)

    if not api_key:
        raise RuntimeError("AI_PROVIDER_GATEWAY_API_KEY must be set.")
    if not available_models:
        raise RuntimeError("TEXT_AVAILABLE_MODELS must contain at least one model.")
    if unknown:
        raise RuntimeError(f"TEXT_AVAILABLE_MODELS contains unknown model(s): {', '.join(sorted(unknown))}")
    if default_model not in available_models:
        raise RuntimeError("TEXT_DEFAULT_MODEL must be included in TEXT_AVAILABLE_MODELS.")

    return Settings(
        api_key=api_key,
        host=os.environ.get("OPENAI_HOST", "127.0.0.1"),
        port=int(os.environ.get("OPENAI_PORT", "8001")),
        state_dir=Path(os.environ.get("AI_PROVIDER_GATEWAY_STATE_DIR", Path.home() / ".local" / "state" / "ai-provider-gateway")),
        default_model=default_model,
        available_models=available_models,
        perplexity_cookies=os.environ.get("PERPLEXITY_COOKIES"),
    )
