from ai_provider_gateway.domain.text_to_text import ResolvedModel


_CHAT_MODELS = (
    ("perplexity/auto", "auto", None),
    ("perplexity/sonar-2", "pro", "sonar"),
    ("perplexity/gpt-4.5", "pro", "gpt-4.5"),
    ("perplexity/gpt-4o", "pro", "gpt-4o"),
    ("perplexity/gpt-5.2", "pro", "gpt-5.2"),
    ("perplexity/gpt-5.6-terra", "pro", "gpt-5.6-terra"),
    ("perplexity/claude-3.7-sonnet", "pro", "claude 3.7 sonnet"),
    ("perplexity/claude-4.5-sonnet", "pro", "claude-4.5-sonnet"),
    ("perplexity/claude-sonnet-5", "pro", "claude-sonnet-5"),
    ("perplexity/gemini-2.0-flash", "pro", "gemini 2.0 flash"),
    ("perplexity/gemini-3.7-flash", "pro", "gemini-3.7-flash"),
    ("perplexity/grok-2", "pro", "grok-2"),
    ("perplexity/grok-4.1", "pro", "grok-4.1"),
    ("perplexity/reasoning", "reasoning", None),
    ("perplexity/r1", "reasoning", "r1"),
    ("perplexity/o3-mini", "reasoning", "o3-mini"),
    ("perplexity/gpt5", "reasoning", "gpt5"),
    ("perplexity/gpt5-thinking", "reasoning", "gpt5_thinking"),
    ("perplexity/gpt-5.2-thinking", "reasoning", "gpt-5.2-thinking"),
    ("perplexity/gpt-5.6-terra-thinking", "reasoning", "gpt-5.6-terra-thinking"),
    ("perplexity/claude-3.7-sonnet-thinking", "reasoning", "claude 3.7 sonnet"),
    ("perplexity/claude-4.5-sonnet-thinking", "reasoning", "claude-4.5-sonnet-thinking"),
    ("perplexity/claude-sonnet-5-thinking", "reasoning", "claude-sonnet-5-thinking"),
    ("perplexity/gemini-3.0-pro", "reasoning", "gemini-3.0-pro"),
    ("perplexity/gemini-3.7-flash-thinking", "reasoning", "gemini-3.7-flash-thinking"),
    ("perplexity/kimi-k2-thinking", "reasoning", "kimi-k2-thinking"),
    ("perplexity/grok-4.1-reasoning", "reasoning", "grok-4.1-reasoning"),
    ("perplexity/deep-research", "deep research", None),
)

_IMAGE_MODELS = (
    ("web-google-flow/nano-banana-2", "Nano Banana 2"),
    ("web-google-flow/nano-banana-pro", "Nano Banana Pro"),
    ("web-google-flow/nano-banana-2-lite", "Nano Banana 2 Lite"),
)

_WEB_PERPLEXITY_MODELS = (
    ("web-perplexity/sonar-2", "sonar-2"),
)

MODELS = {
    id_: ResolvedModel(id_, "perplexity", "chat", provider_model, mode)
    for id_, mode, provider_model in _CHAT_MODELS
} | {
    id_: ResolvedModel(id_, "web-google-flow", "image", provider_model)
    for id_, provider_model in _IMAGE_MODELS
} | {
    id_: ResolvedModel(id_, "web-perplexity", "chat", provider_model)
    for id_, provider_model in _WEB_PERPLEXITY_MODELS
}
ALIASES = {
    "sonar-2": "perplexity/sonar-2",
    "gpt-5.6-terra": "perplexity/gpt-5.6-terra",
    "gpt-5.6-terra-thinking": "perplexity/gpt-5.6-terra-thinking",
    "gemini-3.7-flash": "perplexity/gemini-3.7-flash",
    "gemini-3.7-flash-thinking": "perplexity/gemini-3.7-flash-thinking",
    "claude-sonnet-5": "perplexity/claude-sonnet-5",
    "claude-sonnet-5-thinking": "perplexity/claude-sonnet-5-thinking",
}


def known_model_ids() -> tuple[str, ...]:
    return tuple(MODELS)


def resolve_model(model_id: str | None, default_model: str, available_models: tuple[str, ...], capability: str = "chat") -> ResolvedModel | None:
    selected = ALIASES.get(model_id or default_model, model_id or default_model)
    model = MODELS.get(selected) if selected in available_models else None
    return model if model and model.capability == capability else None


def resolve_chat_model(model_id: str | None, default_model: str, available_models: tuple[str, ...]) -> ResolvedModel | None:
    return resolve_model(model_id, default_model, available_models, "chat")


def resolve_image_model(model_id: str | None, default_model: str, available_models: tuple[str, ...]) -> ResolvedModel | None:
    return resolve_model(model_id, default_model, available_models, "image")


def list_models(available_models: tuple[str, ...]) -> list[ResolvedModel]:
    return [MODELS[model_id] for model_id in available_models]
