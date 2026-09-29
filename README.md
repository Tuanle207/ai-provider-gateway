# Provider Gateway

Provider Gateway is the single HTTP service for browser-backed and client-backed
AI providers. It exposes an OpenAI-compatible API for chat completions, image
generation, model discovery, and authenticated artifact delivery. Provider
accounts, browser sessions, and generated files are kept under
`AI_PROVIDER_GATEWAY_STATE_DIR`; API clients never receive provider filesystem
paths or browser URLs.

All `/v1/*` endpoints require:

```text
Authorization: Bearer <AI_PROVIDER_GATEWAY_API_KEY>
```

## Local Setup

Initialize the vendor dependencies, create local configuration, and install the
gateway with browser support:

```powershell
git submodule update --init --recursive
Copy-Item .env.example .env
# Set AI_PROVIDER_GATEWAY_API_KEY and enabled model allowlists in .env.
uv sync --extra driver
```

To sync the vendor dependencies at any time, run:

```powershell
git submodule update --remote --merge --recursive
```

The gateway loads `.env` automatically for local development. Start it with:

```powershell
uv run ai-provider-gateway
```

It listens on `http://127.0.0.1:8002` by default. Confirm the service and its
enabled models:

```powershell
$headers = @{ Authorization = "Bearer $env:AI_PROVIDER_GATEWAY_API_KEY" }
Invoke-RestMethod http://127.0.0.1:8002/health
Invoke-RestMethod http://127.0.0.1:8002/v1/models -Headers $headers
```

### Provider Login

Provider login is a maintenance operation and is intentionally not exposed over
the HTTP API. Stop the gateway before logging in so only one process writes the
browser account state. Login opens a headed browser; complete the provider login
there and wait for the command to report that the session was saved.

For browser-backed Google Flow:

```powershell
uv run ai-provider-accounts add --provider google_flow --email you@gmail.com
uv run ai-provider-accounts login --provider google_flow --email you@gmail.com
uv run ai-provider-accounts list --provider google_flow
```

For browser-backed Perplexity:

```powershell
uv run ai-provider-accounts add --provider perplexity --email you@example.com
uv run ai-provider-accounts login --provider perplexity --email you@example.com
```

Browser sessions are persisted below:

```text
<AI_PROVIDER_GATEWAY_STATE_DIR>/web-automation/providers/<provider>/sessions/<email>/storage_state.json
```

The existing `perplexity/*` integration is separate from browser-backed
`web-perplexity/*`. Its saved session can be created with:

```powershell
uv run perplexity-login
```

It also supports `PERPLEXITY_COOKIES` when a saved session is not used.

## Production Deployment

On an Ubuntu/Debian VM, clone with both vendor submodules and deploy:

```bash
git clone --recurse-submodules <repository-url> ai-provider-gateway
cd ai-provider-gateway
sudo ./deployment/deploy.sh
```

The first run creates `deployment/production.env` and stops. Set a strong
`AI_PROVIDER_GATEWAY_API_KEY`, configure the enabled model allowlists, then run
the deploy command again. The systemd service loads that file through
`EnvironmentFile`; `.env` is not needed on production.

Verify the deployment:

```bash
curl http://127.0.0.1:8002/health
systemctl status ai-provider-gateway
```

Production stdout and stderr are written to:

```text
/var/lib/ai-provider-gateway/ai-provider-gateway.log
```

The deployment script generates a logrotate policy that rotates daily, retains
30 days, and compresses older logs. Follow the active log with:

```bash
tail -f /var/lib/ai-provider-gateway/ai-provider-gateway.log
```

### Provider Login On A VM

Stop the service before provider login:

```bash
sudo systemctl stop ai-provider-gateway
```

Run account commands as the same service user configured by `RUN_AS_USER` so the
saved session is owned by that account and is written into the production state
directory. The login command needs a headed browser, so run it from a graphical
desktop session or a supported remote-display session such as SSH X11 forwarding.

```bash
sudo -u <service-user> -H env \
  AI_PROVIDER_GATEWAY_STATE_DIR=/var/lib/ai-provider-gateway \
  uv --directory /path/to/ai-provider-gateway run ai-provider-accounts add \
  --provider google_flow --email you@gmail.com

sudo -u <service-user> -H env \
  AI_PROVIDER_GATEWAY_STATE_DIR=/var/lib/ai-provider-gateway \
  DISPLAY="$DISPLAY" \
  uv --directory /path/to/ai-provider-gateway run ai-provider-accounts login \
  --provider google_flow --email you@gmail.com
```

After login completes, restart the service:

```bash
sudo systemctl start ai-provider-gateway
```

Do not run the maintenance CLI and gateway service concurrently against the same
state directory.

## Chat Completion

Send an OpenAI-compatible request:

```powershell
$headers = @{ Authorization = "Bearer $env:AI_PROVIDER_GATEWAY_API_KEY" }
Invoke-RestMethod `
  http://127.0.0.1:8002/v1/chat/completions `
  -Method Post `
  -ContentType application/json `
  -Headers $headers `
  -Body '{"model":"perplexity/sonar-2","messages":[{"role":"user","content":"Hello"}]}'
```

Use `x-conversation-id` to preserve provider conversation state between requests.
Browser-backed Perplexity supports text-only chat and returns a completed answer;
when `stream: true` is requested, the gateway sends one buffered SSE content
delta followed by the OpenAI `[DONE]` marker.

Use the smoke script for local testing:

```powershell
uv run scripts/test_chat_completion.py
```

## Image Generation

Enable a Google Flow model in `.env` or `deployment/production.env`:

```dotenv
IMAGE_DEFAULT_MODEL=web-google-flow/nano-banana-2
IMAGE_AVAILABLE_MODELS=web-google-flow/nano-banana-2
WEB_GOOGLE_FLOW_PROJECTS_FILE=/etc/ai-provider-gateway/google-flow-projects.json
```

Each Google Flow account needs a pool of reusable project IDs. Store the mapping
in a deployment-owned JSON file (see
`deployment/google-flow-projects.json.example`). An account's effective
concurrency is the smaller of its project count and
`WEB_AUTOMATION_PER_ACCOUNT_MAX_CONCURRENT_JOBS`; one active job leases one
project, so concurrent jobs never share a Flow project.

The supported request fields are `model`, `prompt`, `n`, `size`, and
`response_format`. `n` must be from 1 through 4. Supported sizes are:

```text
1024x1024  768x1024  1024x768  768x1376  1376x768
```

`response_format` accepts `b64_json` or `url`. URL responses require
`AI_PROVIDER_GATEWAY_PUBLIC_BASE_URL` and point to authenticated gateway artifact
routes, not provider download URLs.

Test image generation and save `b64_json` responses locally:

```powershell
uv run scripts/test_image_generation.py
```

Override the script's model, prompt, size, count, output directory, or response
format with `AI_PROVIDER_GATEWAY_IMAGE_MODEL`, `AI_PROVIDER_GATEWAY_PROMPT`,
`AI_PROVIDER_GATEWAY_IMAGE_SIZE`, `AI_PROVIDER_GATEWAY_IMAGE_COUNT`,
`AI_PROVIDER_GATEWAY_IMAGE_OUTPUT_DIR`, and
`AI_PROVIDER_GATEWAY_IMAGE_RESPONSE_FORMAT`.

## Troubleshooting Failures

Every response carries an `X-Request-ID` header. Send your own (1–64 characters
of `A-Z a-z 0-9 _ -`) or let the gateway generate one. Error bodies include it
as `error.request_id`, and every log line emitted while serving the request
carries `request_id=...`.

Provider failures map to these errors:

| Cause | HTTP | `error.code` |
| --- | --- | --- |
| No provider account available | 503 | `no_available_account` |
| Provider quota exhausted | 429 | `provider_quota_exceeded` |
| Generation timed out | 504 | `provider_timeout` |
| Provider account must sign in again | 503 | `provider_auth_required` |
| Any other provider failure | 502 | `provider_error` |

When a browser-automation attempt fails, the gateway always captures the
failing page: a screenshot, the page HTML, and `meta.json`. The metadata holds
the step, error, traceback, recent console errors, failed network requests and
step timings. Successful attempts write nothing. Captures are stored in:

```text
$AI_PROVIDER_GATEWAY_STATE_DIR/web-automation/failures/<YYYY-MM-DD>/<HHMMSS>_<request_id>_a<attempt>/
```

To find the capture for a failed request on the VM:

```bash
grep '<request_id>' "$AI_PROVIDER_GATEWAY_STATE_DIR/ai-provider-gateway.log" | grep attempt_failed
scp -r vm:/var/lib/ai-provider-gateway/web-automation/failures/<date>/<capture_id> .
```

Captures show logged-in provider pages, so the directory is owner-only (0700).
It never contains cookies, storage state, response bodies or prompt text.
Captures older than 7 days are pruned automatically, as are the oldest ones
once the directory exceeds 500 MB.

Set `AI_PROVIDER_GATEWAY_LOG_JSON=true` for JSON log lines, and
`AI_PROVIDER_GATEWAY_LOG_LEVEL` (default `INFO`) to change verbosity.

## Integrations

| Public provider | Models | Implementation | Authentication and state |
| --- | --- | --- | --- |
| `perplexity` | `perplexity/*` | Vendored `perplexity-ai` client | `perplexity-login` or `PERPLEXITY_COOKIES`; state in the gateway state directory. |
| `web-perplexity` | `web-perplexity/*` | Vendored `ai-web-provider` Perplexity browser automation | `ai-provider-accounts`; provider accounts and browser storage state below `web-automation/`. |
| `web-google-flow` | `web-google-flow/*` | Vendored `ai-web-provider` Google Flow browser automation | `ai-provider-accounts`; generated artifacts below `web-automation/outputs/`. |

The gateway owns HTTP authentication, OpenAI-compatible validation and response
conversion, model allowlists, conversation persistence, artifact URLs, and
artifact delivery. `vendor/ai-web-provider` owns provider accounts, account
rotation, browser lifecycle, browser sessions, and provider-specific automation.
