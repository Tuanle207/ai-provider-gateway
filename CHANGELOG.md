# Changelog

All notable changes to this project are documented in this file.

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
