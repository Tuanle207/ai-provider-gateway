# AI Web Provider Integration Design

## Status

Proposed.

## Summary

`ai-provider-gateway` remains the only HTTP service and the only public
OpenAI-compatible API. It will vendor `ai-web-provider` as a Git submodule and
import its runtime directly in-process.

`ai-web-provider` is the renamed successor to `ai-proxy`. It provides browser
automation, account persistence, account rotation, browser-session lifecycle,
and provider implementations. It does not expose an HTTP API after this
change.

The gateway keeps its existing client-based Perplexity integration unchanged.
It adds two new gateway integration packages backed by the `ai-web-provider`
vendor:

| Public provider | Gateway integration | Vendor implementation | Capability |
| --- | --- | --- | --- |
| `perplexity` | `integrations/perplexity` | `vendor/perplexity-ai` | Chat |
| `web-perplexity` | `integrations/web_perplexity` | `vendor/ai-web-provider` Perplexity automation | Chat |
| `web-google-flow` | `integrations/web_google_flow` | `vendor/ai-web-provider` Google Flow automation | Image generation |

The provider names deliberately distinguish the existing Perplexity API-client
path from browser-driven Perplexity. They may use distinct authentication,
session, account, and quota state.

## Goals

- Add `ai-web-provider` as a Git submodule in `vendor/`.
- Rename the former `ai-proxy` project and Python package to
  `ai-web-provider` and `ai_web_provider`.
- Remove the standalone FastAPI/API layer from `ai-web-provider`.
- Reuse its provider runtime, account management, account rotation, browser
  lifecycle, Perplexity automation, and Google Flow automation in-process.
- Keep the existing `integrations/perplexity` implementation and
  `vendor/perplexity-ai` submodule working without behavior changes.
- Add OpenAI-compatible chat support for browser-backed Perplexity.
- Add OpenAI-compatible text-to-image support for Google Flow.
- Return fully qualified, gateway-owned artifact URLs for image URL responses.
- Keep model selection explicit, capability-aware, and allowlisted.

## Non-Goals

- Replacing the existing `perplexity/*` implementation.
- Keeping an HTTP server, API key, routers, or OpenAI API in
  `ai-web-provider`.
- Token-by-token streaming from browser automation.
- Arbitrary model labels supplied by API callers.
- OpenAI Images edits, variations, masks, URL input images, or undocumented
  request fields in the initial implementation.
- Reference-image generation until uploaded media can be resolved safely into
  local `TaskRequest.inputs` paths.
- Making Google Flow project reuse safe under parallel execution without an
  explicit project-level concurrency policy.

## Architecture

```text
OpenAI-compatible client
        |
        v
ai-provider-gateway (sole HTTP service)
  |- /v1/chat/completions
  |- /v1/images/generations
  |- /v1/models
  |- /v1/artifacts/{artifact_id}
  |
  +-- integrations/perplexity
  |     `-- vendor/perplexity-ai
  |
  +-- integrations/web_perplexity
  |     `-- vendor/ai-web-provider
  |           |- accounts and rotation
  |           |- Camoufox browser runtime
  |           `- Perplexity website automation
  |
  `-- integrations/web_google_flow
        `-- vendor/ai-web-provider
              |- accounts and rotation
              |- Camoufox browser runtime
              `- Google Flow website automation
```

The gateway owns all transport concerns:

- Bearer authentication.
- OpenAI request validation and error envelopes.
- Model discovery and allowlists.
- OpenAI response conversion.
- Artifact registration, URL generation, access control, and delivery.
- Gateway lifespan and shutdown ordering.

`ai-web-provider` owns all browser-provider runtime concerns:

- Provider discovery and provider specifications.
- Account storage, state, cooldowns, and health state.
- Account-slot selection and rotation.
- Browser context creation, persisted browser state, and warm browser cleanup.
- Provider sessions, page automation, and task execution.
- Provider-specific browser code for Perplexity and Google Flow.

## Git Submodule And Package Contract

### Gateway vendor layout

```text
ai-provider-gateway/
  vendor/
    perplexity-ai/       # Existing submodule; remains in use.
    ai-web-provider/     # New submodule; renamed former ai-proxy project.
```

The gateway `.gitmodules` file will contain an entry equivalent to:

```ini
[submodule "vendor/ai-web-provider"]
	path = vendor/ai-web-provider
	url = <ai-web-provider Git remote>
```

The actual remote URL must be selected before implementation. It must be a
standalone Git repository reachable by deployment hosts. A local filesystem
path is not sufficient for production submodule initialization.

Deployment continues to use:

```bash
git submodule update --init --recursive
```

### Python dependencies

The gateway imports the submodule as an editable local dependency:

```toml
[project]
dependencies = [
    "ai-web-provider",
    "perplexity-api",
]

[tool.uv.sources]
ai-web-provider = { path = "vendor/ai-web-provider", editable = true }
perplexity-api = { path = "vendor/perplexity-ai", editable = true }
```

The final dependency list retains all existing gateway dependencies. The
gateway Python requirement must be raised to the version required by
`ai-web-provider` (currently Python 3.11 or newer) if that remains true after
the rename.

## AI Web Provider Rename And API Removal

### Rename

```text
ai-proxy/                 -> ai-web-provider/
src/ai_proxy/             -> src/ai_web_provider/
ai-proxy                  -> ai-web-provider       (distribution name)
ai_proxy.*                -> ai_web_provider.*     (import namespace)
AI_PROXY_*                -> AI_WEB_PROVIDER_*     (standalone config namespace)
ai_proxy.providers        -> ai_web_provider.providers (entry-point group)
```

The rename applies to all production code, tests, build configuration,
provider plug-in entry points, documentation, and command names. No compatibility
import package should be added unless there are identified external consumers
that require a temporary migration period.

### Remove HTTP-only modules

Delete the former API layer rather than moving it into the renamed package:

```text
ai_web_provider/core/service/app.py
ai_web_provider/core/service/deps.py
ai_web_provider/core/service/errors.py
ai_web_provider/core/service/routers/
```

Remove the old API server entry point, API key generation/persistence, CORS,
request-ID middleware, server host/port settings, and generated API server
scripts. Remove `fastapi` and `uvicorn` from the base package dependencies.

The former API routers are not reusable integration boundaries. Their request
models, FastAPI exceptions, output URL construction, and authentication all
belong in `ai-provider-gateway`.

### Retain And Relocate Runtime Wiring

The former `core/service/container.py` constructs reusable runtime objects but
is in an HTTP-named package and owns API-key behavior. Move it to a neutral
location, for example:

```text
ai_web_provider/runtime/container.py
```

Rename `ServiceContainer` to `ProviderRuntimeContainer`. It retains provider
discovery, `ProviderRuntime`, `AccountManager`, `AccountSlotPool`,
`CamoufoxBackend`, shared browser capacity, provider settings, and shutdown.
It removes API-key resolution and all HTTP assumptions.

Its public lifecycle is transport-neutral:

```python
class ProviderRuntimeContainer:
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
    def provider(self, name: str) -> ProviderRuntime: ...
```

`shutdown()` must close every warm browser backend. The gateway must always
await it during its FastAPI lifespan shutdown.

### Extract Provider Execution

The old HTTP chat and image routers currently contain the browser execution
sequence. Before deleting them, move that sequence into a runtime facade such
as `ai_web_provider/runtime/executor.py`.

The executor accepts a `TaskRequest` and runs:

1. Resolve the requested provider runtime.
2. Acquire an account slot, passing the provider model for model-specific
   quota selection when applicable.
3. Load the selected account.
4. Open an account browser context and page.
5. Build a `ProviderSession`.
6. Call the provider adapter.
7. Close the page and release the account slot in `finally` blocks.
8. Record success or failure on the account manager.
9. Apply failure policy status/cooldown effects.
10. Retry eligible failures according to configured retry policy and available
    accounts.

The executor must not accept HTTP request objects or produce HTTP responses.

## Gateway Runtime Integration

Add a small gateway wrapper around the vendor runtime:

```text
src/ai_provider_gateway/integrations/web_runtime/
  __init__.py
  runtime.py
  dispatcher.py
```

`WebProviderRuntime` creates the vendor `ProviderRuntimeContainer`, starts it
during gateway startup, and closes it during gateway shutdown. It maps
gateway-owned configuration into the vendor settings model. The gateway should
not require operators to configure an independent API/server configuration for
the vendored package.

`ProviderDispatcher` invokes the vendor runtime executor. It may be a thin
wrapper if retry and account-effect behavior are fully implemented in the
vendor executor. There must be exactly one owner of retries and account-state
effects; duplicating them in both packages would cause double cooldowns or
double success/failure accounting.

## Provider Integrations

### Existing Perplexity

The following remain unchanged and active:

```text
src/ai_provider_gateway/integrations/perplexity/
vendor/perplexity-ai/
PERPLEXITY_COOKIES
perplexity-login command
```

Public models in this path retain the `perplexity/*` namespace. Their existing
conversation persistence, streaming behavior, client initialization, and
model overrides continue to work as they do now.

### Web Perplexity

Create:

```text
src/ai_provider_gateway/integrations/web_perplexity/
  __init__.py
  adapter.py
  models.py
```

`WebPerplexityTextToTextAdapter` implements the gateway `TextToTextProvider`
protocol. It translates a gateway request to a vendor task:

```python
TaskRequest(
    provider="perplexity",
    kind=TaskKind.TEXT,
    prompt=rendered_prompt,
    count=1,
    timeout=configured_timeout,
    params={"model": request.model.provider_model},
    workspace_ref=stored_workspace_ref,
)
```

The vendor Perplexity provider name remains `perplexity`; the gateway provider
name is `web-perplexity`. This avoids renaming provider internals while making
the public gateway routing explicit.

When the vendor task returns a `workspace_ref`, persist it in the existing
gateway `ConversationStore` as provider state:

```json
{"workspace_ref":"..."}
```

On a later request with the same `x-conversation-id`, restore that workspace
reference. Browser automation currently returns a completed answer rather than
token deltas. `stream: true` may use valid OpenAI SSE framing with one buffered
content delta, followed by `finish_reason: "stop"` and `[DONE]`; it must not be
described as token streaming.

The initial implementation supports text-only chat content. Reject tool calls,
audio, images, and unrecognized multipart content instead of silently dropping
it.

### Web Google Flow

Create:

```text
src/ai_provider_gateway/integrations/web_google_flow/
  __init__.py
  adapter.py
  models.py
```

Add a dedicated image-generation domain protocol in the gateway. Do not put
image generation into `TextToTextProvider`.

`WebGoogleFlowImageAdapter` translates an OpenAI image request into:

```python
TaskRequest(
    provider="google_flow",
    kind=TaskKind.IMAGE,
    prompt=request.prompt,
    count=request.n,
    timeout=configured_timeout,
    params={
        "model": request.model.provider_model,
        "aspect_ratio": aspect_ratio,
        "reuse_default_project": reuse_default_project,
    },
)
```

It passes `request.model.provider_model` into account-slot acquisition so
model-specific quota cooldowns are honored.

The initial OpenAI-compatible image subset is:

```json
{
  "model": "web-google-flow/nano-banana-2",
  "prompt": "A cinematic landscape at dawn",
  "n": 1,
  "size": "1024x1024",
  "response_format": "url"
}
```

Supported mappings are:

| OpenAI size | Google Flow aspect ratio |
| --- | --- |
| `1024x1024` | `1:1` |
| `768x1024` | `3:4` |
| `1024x768` | `4:3` |
| `768x1376` | `9:16` |
| `1376x768` | `16:9` |

Validate `n` in the range 1 through 4. Reject unsupported sizes,
`response_format` values other than `url` and `b64_json`, and unsupported
OpenAI Images fields explicitly.

Do not expose reference-image fields until media upload and artifact resolution
are implemented end-to-end. Accepting a field that does not reach
`TaskRequest.inputs` is incorrect.

## Model Registry And Routing

Replace the text-only registry with capability-aware model descriptors. A
descriptor contains at least:

```python
id: str
provider: str
capability: Literal["chat", "image"]
provider_model: str | None
mode: str | None
```

Recommended initial namespaces:

```text
perplexity/sonar-2
perplexity/...                    # Existing implementation, unchanged

web-perplexity/sonar-2
web-perplexity/...                # Browser-backed Perplexity

web-google-flow/nano-banana-2
web-google-flow/nano-banana-pro
web-google-flow/nano-banana-2-lite
```

Each public model maps to a known tested provider label. The gateway must not
forward arbitrary Google Flow labels because UI selection can otherwise retain
a previous site setting while reporting a requested but unselected model.

Add capability-specific resolution methods:

```python
resolve_chat_model(...)
resolve_image_model(...)
list_models(...)
```

`/v1/models` returns all enabled models. Chat and image routes reject models
that do not support the route capability.

Configuration separates capabilities:

```text
CHAT_DEFAULT_MODEL
CHAT_AVAILABLE_MODELS
IMAGE_DEFAULT_MODEL
IMAGE_AVAILABLE_MODELS
```

During a migration, `TEXT_DEFAULT_MODEL` and `TEXT_AVAILABLE_MODELS` may remain
accepted as aliases for the chat variables. New `CHAT_*` variables take
precedence when both are set.

## Gateway API And Artifact Delivery

### Image generation endpoint

Add:

```text
POST /v1/images/generations
```

Return the OpenAI Images response envelope:

```json
{
  "created": 1760000000,
  "data": [
    {"url":"https://ai.example.com/v1/artifacts/artifact-abc123"}
  ]
}
```

or, when `response_format` is `b64_json`:

```json
{
  "created": 1760000000,
  "data": [
    {"b64_json":"..."}
  ]
}
```

### Full URL requirement

URL responses must be fully qualified gateway URLs. They must never expose a
relative vendor `/download/...` path, an internal vendor host, or a filesystem
path.

Add:

```text
AI_PROVIDER_GATEWAY_PUBLIC_BASE_URL=https://ai.example.com
```

Requirements:

- The value must be an absolute `http://` or `https://` URL.
- Normalize a trailing slash before appending artifact paths.
- Require this setting whenever `response_format` is `url`.
- Do not derive it from an inbound `Host` header. Reverse proxies and untrusted
  host headers can create invalid or attacker-controlled output URLs.
- `b64_json` responses do not require this setting.

### Artifact store

Add a gateway-owned artifact store, for example:

```text
src/ai_provider_gateway/infrastructure/artifact_store.py
```

The store must:

- Validate that returned vendor paths are relative and resolve below the
  configured web-provider outputs directory.
- Register an opaque artifact ID.
- Persist relative path, MIME type, byte size, hash, dimensions, creation time,
  and expiry policy.
- Serve files through `GET /v1/artifacts/{artifact_id}`.
- Never let callers supply arbitrary paths or filenames.

Artifact delivery remains gateway-authenticated. If public or expiring signed
links are needed later, they are a separate product/security decision.

## Configuration And State

The gateway remains the operator-facing configuration boundary. It maps
gateway settings into `ai_web_provider` settings directly rather than requiring
operators to configure a second standalone web-provider service.

Gateway settings include:

```text
AI_PROVIDER_GATEWAY_API_KEY
AI_PROVIDER_GATEWAY_STATE_DIR
AI_PROVIDER_GATEWAY_PUBLIC_BASE_URL
OPENAI_HOST
OPENAI_PORT

CHAT_DEFAULT_MODEL
CHAT_AVAILABLE_MODELS
IMAGE_DEFAULT_MODEL
IMAGE_AVAILABLE_MODELS

WEB_AUTOMATION_DATA_DIR
WEB_AUTOMATION_HEADLESS
WEB_AUTOMATION_MAX_CONCURRENT_BROWSERS
WEB_AUTOMATION_PER_ACCOUNT_CONCURRENCY
WEB_AUTOMATION_BROWSER_IDLE_TTL_SECONDS
WEB_AUTOMATION_DEFAULT_TIMEOUT_SECONDS
WEB_AUTOMATION_MAX_RETRIES
WEB_AUTOMATION_COOLDOWN_MINUTES

WEB_PERPLEXITY_*
WEB_GOOGLE_FLOW_*
```

The default web-provider state directory is:

```text
<AI_PROVIDER_GATEWAY_STATE_DIR>/web-automation/
  providers/perplexity/accounts.yaml
  providers/perplexity/sessions/<email>/storage_state.json
  providers/google_flow/accounts.yaml
  providers/google_flow/sessions/<email>/storage_state.json
  providers/google_flow/default_projects.json
  providers/google_flow/reference_cache.json
  outputs/
```

Existing state under the former project must be migrated deliberately or the
new data directory must initially point to it. Changing the root directory
without migration makes browser sessions and accounts appear missing, forcing
interactive login again.

Only one process may write a given web-provider data directory. Do not run the
old standalone process and the embedded gateway against the same provider
accounts, browser storage state, or Google Flow caches.

## Account Administration

Interactive login must not be exposed through the OpenAI HTTP API. Provide
separate maintenance commands in the gateway, or a non-HTTP maintenance CLI in
the vendor runtime, for:

```text
accounts add --provider perplexity --email <email>
accounts login --provider perplexity --email <email>
accounts add --provider google_flow --email <email>
accounts login --provider google_flow --email <email>
```

These commands use the vendor `AccountManager`, provider authentication
implementation, and a headed browser context. They persist browser storage
state in `WEB_AUTOMATION_DATA_DIR`.

## Google Flow Safety Requirements

The current Google Flow automation needs correctness work before it becomes a
gateway image vendor:

1. Capture existing image URLs before submitting a prompt to a reused project.
2. Return only URLs created by the current generation.
3. Fail when fewer artifacts than requested are produced instead of returning
   stale or partial results silently.
4. Serialize requests using the same default Flow project. Start with one
   concurrent Google Flow generation per account, or use isolated projects.
5. Surface model, aspect-ratio, and count selection failures. Do not silently
   generate using the site UI's previous setting.
6. Ensure output extension and MIME metadata describe the actual downloaded
   content.

These are provider-runtime fixes in `ai-web-provider`, not gateway transport
logic.

## Lifecycle And Error Mapping

Gateway startup order:

1. Load and validate gateway configuration and enabled models.
2. Construct the web-provider settings and runtime container.
3. Await web-provider runtime startup.
4. Open conversation and artifact stores.
5. Construct the existing Perplexity, web Perplexity, and web Google Flow
   adapters/application services.
6. Publish the fully constructed service container on `app.state`.

Gateway shutdown order:

1. Stop dispatching new work.
2. Close gateway stores.
3. Await web-provider runtime shutdown to close all warm browser contexts.
4. Clear gateway application state.

Map provider failures without exposing account emails, local paths, browser
URLs, selectors, or raw provider errors:

| Condition | Status | Error code |
| --- | --- | --- |
| Invalid request or capability mismatch | 400 | `invalid_request_error` |
| Disabled or unknown model | 404 | `model_not_found` |
| No usable provider account | 503 | `service_unavailable` |
| Quota/cooldown exhausted | 429 | `rate_limit_exceeded` |
| Provider/browser automation failure | 502 | `provider_error` |
| Provider timeout | 504 | `timeout` |

## Implementation Plan

### Phase 1: Prepare the ai-web-provider repository

1. Create or rename the standalone repository from `ai-proxy` to
   `ai-web-provider`.
2. Rename the distribution and import namespace to `ai-web-provider` and
   `ai_web_provider`.
3. Update all internal/test imports and provider entry-point metadata.
4. Move the reusable container to `runtime/container.py` and remove API-key
   ownership.
5. Extract a transport-neutral provider executor from the old chat/image
   routers.
6. Move failure/account effect handling into the executor if it is not already
   centralized.
7. Delete the FastAPI app, routers, middleware, API error handlers, server
   settings, API entry point, and FastAPI/Uvicorn dependencies.
8. Update documentation to describe a library/runtime and non-HTTP account
   maintenance workflow.
9. Run the renamed vendor test suite without FastAPI/Uvicorn installed.

### Phase 2: Vendor it in the gateway

1. Add `vendor/ai-web-provider` as a Git submodule.
2. Update `.gitmodules`, gateway packaging, lockfile, and deployment script.
3. Keep `vendor/perplexity-ai` and its dependency configuration unchanged.
4. Raise the gateway Python version if required by the web-provider vendor.
5. Add an explicit deployment/update step that initializes both submodules.

### Phase 3: Add gateway runtime infrastructure

1. Add `integrations/web_runtime`.
2. Construct and stop the vendor runtime in the gateway FastAPI lifespan.
3. Map gateway configuration to the vendor settings and data path.
4. Add unit tests for browser/page/slot cleanup, retries, and account effects.
5. Add non-HTTP account management/login commands and documentation.

### Phase 4: Add web Perplexity chat

1. Add `integrations/web_perplexity`.
2. Register explicit `web-perplexity/*` chat models.
3. Add provider-aware chat dispatch while retaining the existing
   `perplexity/*` path unmodified.
4. Persist vendor workspace references through the existing conversation
   store.
5. Implement buffered SSE behavior for browser-backed `stream: true`.
6. Add adapter, conversation, model routing, and error-mapping tests.

### Phase 5: Add web Google Flow image generation

1. Add a gateway image-generation domain contract and application service.
2. Add `integrations/web_google_flow`.
3. Add image-capable model registry entries and capability-specific allowlists.
4. Add `POST /v1/images/generations` validation and response conversion.
5. Add the gateway artifact store and authenticated artifact delivery route.
6. Implement fully qualified URL generation using
   `AI_PROVIDER_GATEWAY_PUBLIC_BASE_URL`.
7. Implement the Google Flow safety requirements before enabling image models
   in production.
8. Add unit/API contract tests and a separately marked real-browser smoke
   test.

### Phase 6: Documentation and deployment

1. Update `.env.example` and production environment templates.
2. Document provider names, public models, state directories, account login,
   buffered streaming, image limitations, and artifact URL behavior.
3. Update deployment documentation for both submodules and browser runtime
   prerequisites.
4. Add changelog entries when the implementation is released.

## Verification Criteria

### Vendor package

- `ai_web_provider` imports and its runtime/provider tests pass without
  FastAPI or Uvicorn installed.
- Provider discovery finds the renamed built-in providers.
- The runtime executor always closes pages and releases slots, including on
  adapter exceptions.
- Account success, failure, cooldown, needs-login, and model quota effects are
  applied exactly once.

### Existing Perplexity preservation

- The existing `perplexity/*` models appear in `/v1/models` when enabled.
- Existing Perplexity chat completion, conversation persistence, and streaming
  tests pass unchanged.
- `PERPLEXITY_COOKIES` and `perplexity-login` continue to work.

### Web Perplexity

- A `web-perplexity/*` model invokes the vendor Perplexity runtime.
- The provider model label is translated correctly.
- The workspace reference is persisted and reused for the same
  `x-conversation-id`.
- Buffered SSE output follows OpenAI SSE framing and ends with `[DONE]`.

### Web Google Flow

- Only enabled `web-google-flow/*` models resolve on the image endpoint.
- Valid sizes map to the expected aspect ratio; invalid values are rejected.
- `n` greater than four is rejected.
- URL results are fully qualified gateway artifact URLs.
- `b64_json` results decode to the registered artifact bytes.
- Artifact access cannot traverse outside the configured output root.
- Default project reuse cannot return prior-generation images.

### API compatibility

- Every versioned endpoint requires the gateway Bearer API key.
- Error responses retain the gateway's OpenAI-compatible envelope.
- Models from the wrong capability return a clear model/capability error.
- No `ai-web-provider` HTTP endpoint, API key, relative download URL, or
  internal path is exposed to API clients.

## Risks And Decisions To Resolve

1. Select and publish the Git remote for the `vendor/ai-web-provider`
   submodule.
2. Confirm the final Python minimum version for `ai-web-provider`; the gateway
   must support it.
3. Decide whether `web-perplexity` initially uses the same public model set as
   `perplexity`, or a smaller explicit set.
4. Decide whether Google Flow uses isolated projects per request or serialized
   default-project reuse. Default-project reuse must be serialized until stale
   result isolation is implemented and verified.
5. Decide the artifact URL access policy. This design uses gateway Bearer
   authentication. Public or signed URLs require separate security design.
6. Decide the state migration procedure for existing account/browser data
   before changing the default data root.
