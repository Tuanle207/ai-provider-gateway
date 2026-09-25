"""Gateway-owned Perplexity wire-model overrides.

These values are private to the Perplexity integration. They extend the
unmodified upstream ``perplexity.config.MODEL_MAPPINGS`` at runtime.
"""

MODEL_MAPPING_OVERRIDES = {
    "pro": {
        "gpt-5.6-terra": "gpt56_terra",
        "gemini-3.7-flash": "gemini37flash",
        "claude-sonnet-5": "claude50sonnet",
    },
    "reasoning": {
        "gpt-5.6-terra-thinking": "gpt56_terra_thinking",
        "gemini-3.7-flash-thinking": "gemini37flashthinking",
        "claude-sonnet-5-thinking": "claude50sonnetthinking",
    },
}


def apply_model_overrides() -> None:
    """Extend upstream mappings in memory without modifying the submodule."""
    from perplexity.config import MODEL_MAPPINGS

    for mode, mappings in MODEL_MAPPING_OVERRIDES.items():
        MODEL_MAPPINGS[mode].update(mappings)
