# AI Provider Gateway

An OpenAI-compatible AI gateway. The first supported capability is text-to-text
through an in-process Perplexity adapter backed by the pinned
`vendor/perplexity-ai` Git submodule.

## Run

```powershell
uv sync --extra driver
uv run perplexity-login
uv run ai-provider-gateway
```

The service listens on `127.0.0.1:8001` by default. Set `OPENAI_HOST` and
`OPENAI_PORT` to override this. Set `TEXT_DEFAULT_MODEL` to choose the default
allowlisted model; it defaults to `perplexity/sonar-2`.

```powershell
curl http://127.0.0.1:8001/v1/models
curl http://127.0.0.1:8001/v1/chat/completions -Method POST -ContentType application/json -Body '{"model":"perplexity/sonar-2","messages":[{"role":"user","content":"Hello"}]}'
```

Call the local chat API with the included smoke script:

```powershell
uv run scripts/test_chat_completion.py
```

Set `AI_PROVIDER_GATEWAY_URL`, `AI_PROVIDER_GATEWAY_MODEL`, or
`AI_PROVIDER_GATEWAY_PROMPT` to override its target, model, or prompt.

Use `x-perplexity-conversation-id` to retain Perplexity follow-up state between
requests. The gateway persists opaque provider state in SQLite.

## Upstream Updates

```powershell
git submodule update --remote vendor/perplexity-ai
uv sync
uv run scripts/test_chat_completion.py
```

Compatibility changes belong in `src/ai_provider_gateway/integrations/perplexity`,
not in the submodule.

Perplexity wire-model customizations belong in
`integrations/perplexity/model_overrides.py`. They are applied in memory when
the adapter creates its upstream client, leaving the submodule unmodified.
