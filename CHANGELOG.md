# Changelog

All notable changes to this project are documented in this file.

## [0.2.1] - 2026-09-29

### Added

- `X-Request-ID` correlation: accepted or generated per request, returned on every response and in error bodies, bound to all log lines, and passed to ai-web-provider tasks.
- Automatic failure captures for browser-automation attempts (screenshot, HTML, metadata) under `web-automation/failures/`, with automatic pruning.
- `AI_PROVIDER_GATEWAY_LOG_JSON` and `AI_PROVIDER_GATEWAY_LOG_LEVEL`.

### Changed

- Image generation failures are logged and mapped to specific status codes (`no_available_account`, `provider_quota_exceeded`, `provider_timeout`, `provider_auth_required`, `provider_error`). 5xx errors use `type: server_error`.
- Tracebacks no longer include local variables.

### Fixed

- The env templates and docs used `WEB_AUTOMATION_PER_ACCOUNT_MAX_CONCURRENT_JOB`, which is ignored. The setting is `WEB_AUTOMATION_PER_ACCOUNT_MAX_CONCURRENT_JOBS`.

## [0.2.0] - 2026-09-27

### Added

- Integrated web ai provider to support chat-completions, image generation.
- Improved logging.
- Additional environment configuration options for the web ai provider.

## [0.1.0] - 2026-09-25

### Added

- OpenAI-compatible chat-completions gateway backed by Perplexity.
- Required bearer-token authentication for versioned API endpoints.
- Configurable `TEXT_AVAILABLE_MODELS` allowlist and default model.
- Health endpoint reporting the running service version.
- Local and production environment templates.
- Idempotent Ubuntu/Debian systemd deployment script.
