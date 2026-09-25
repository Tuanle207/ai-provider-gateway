# AI Provider Gateway

An OpenAI-compatible AI gateway. The first supported capability is text-to-text
through an in-process Perplexity adapter backed by the pinned
`vendor/perplexity-ai` Git submodule.

## Local Run

```powershell
Copy-Item .env.example .env
# Set AI_PROVIDER_GATEWAY_API_KEY in .env, then load the file into your shell.
Get-Content .env | Where-Object { $_ -and -not $_.StartsWith('#') } | ForEach-Object { $name, $value = $_ -split '=', 2; Set-Item -Path "Env:$name" -Value $value }
uv sync --extra driver
uv run perplexity-login
uv run ai-provider-gateway
```

The service listens on `127.0.0.1:8001` by default. All `/v1/*` requests require
`Authorization: Bearer <AI_PROVIDER_GATEWAY_API_KEY>`. Set `OPENAI_HOST` and
`OPENAI_PORT` to override the listener. `TEXT_DEFAULT_MODEL` selects the default
model and must be included in `TEXT_AVAILABLE_MODELS`. The latter is a
comma-separated public-model allowlist; omit it to allow every built-in model.

```powershell
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/v1/models -Headers @{ Authorization = "Bearer $env:AI_PROVIDER_GATEWAY_API_KEY" }
curl http://127.0.0.1:8001/v1/chat/completions -Method POST -ContentType application/json -Headers @{ Authorization = "Bearer $env:AI_PROVIDER_GATEWAY_API_KEY" } -Body '{"model":"perplexity/sonar-2","messages":[{"role":"user","content":"Hello"}]}'
```

Call the local chat API with the included smoke script:

```powershell
uv run scripts/test_chat_completion.py
```

Set `AI_PROVIDER_GATEWAY_URL`, `AI_PROVIDER_GATEWAY_MODEL`, or
`AI_PROVIDER_GATEWAY_PROMPT` to override its target, model, or prompt.

Use `x-perplexity-conversation-id` to retain Perplexity follow-up state between
requests. The gateway persists opaque provider state in SQLite.

## Production Deployment

On an Ubuntu/Debian VM, clone this repository including its submodule and run:

```bash
git clone --recurse-submodules <repository-url> ai-provider-gateway
cd ai-provider-gateway
sudo deployment/deploy.sh
```

The first run creates `/etc/ai-provider-gateway.env` and stops so no insecure
service can start. Set a strong `AI_PROVIDER_GATEWAY_API_KEY` in that file, then
rerun `sudo deployment/deploy.sh`. Later invocations update submodules,
dependencies, the systemd unit, and restart the service while preserving the
environment file and `/var/lib/ai-provider-gateway` state.

Use `RUN_AS_USER`, `APP_DIR`, `ENV_FILE`, `PORT`, or `WORKERS` to override the
deployment defaults. Verify the running release with:

```bash
curl http://127.0.0.1:8001/health
systemctl status ai-provider-gateway
```

For a saved Perplexity browser session, run `uv run perplexity-login` as the
configured service user after deployment; it is stored under the configured
`AI_PROVIDER_GATEWAY_STATE_DIR`. Alternatively configure `PERPLEXITY_COOKIES` in
the production environment file.

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
