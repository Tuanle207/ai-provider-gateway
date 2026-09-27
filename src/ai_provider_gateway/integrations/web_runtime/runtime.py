from pathlib import Path

from ai_web_provider import ProviderExecutor, ProviderRuntimeContainer, Settings
from ai_proxy.core.models import Account, AccountStatus
from ai_proxy.core.provider.session import ProviderSession


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

    def add_account(self, provider: str, email: str) -> Account:
        return self._container.provider(provider).accounts.add(email)

    def list_accounts(self, provider: str) -> list[Account]:
        return self._container.provider(provider).accounts.list_accounts()

    async def login(self, provider: str, email: str) -> None:
        runtime = self._container.provider(provider)
        account = runtime.accounts.get(email)
        session = ProviderSession(
            account=account,
            page=None,
            paths=self._container.paths,
            output_dir=self._container.paths.outputs_dir,
            settings=runtime.settings,
        )
        if not await runtime.auth.interactive_login(session):
            raise RuntimeError("Login did not complete before the provider timeout.")
        runtime.accounts.set_status(account.email, AccountStatus.ACTIVE)
