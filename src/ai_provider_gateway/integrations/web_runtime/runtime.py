from pathlib import Path

from ai_web_provider import ProviderExecutor, ProviderRuntimeContainer, Settings


class WebProviderRuntime:
    def __init__(self, state_dir: Path, *, headless: bool, max_concurrent_browsers: int, per_account_concurrency: int, default_timeout_seconds: float, max_retries: int, cooldown_minutes: int, provider_settings: dict[str, dict]) -> None:
        settings = Settings(
            data_dir=str(state_dir / "web-automation"),
            headless=headless,
            max_concurrent_browsers=max_concurrent_browsers,
            per_account_concurrency=per_account_concurrency,
            default_timeout_seconds=default_timeout_seconds,
            max_retries=max_retries,
            cooldown_minutes=cooldown_minutes,
            providers=provider_settings,
        )
        self._container = ProviderRuntimeContainer(settings)
        self.dispatcher = ProviderExecutor(self._container)

    @property
    def output_dir(self) -> Path:
        return self._container.paths.outputs_dir

    async def startup(self) -> None:
        await self._container.startup()

    async def shutdown(self) -> None:
        await self._container.shutdown()
