"""Non-HTTP account administration for browser-backed providers."""

import argparse
import asyncio

from ai_provider_gateway.config import settings
from ai_provider_gateway.integrations.registry import known_model_ids
from ai_provider_gateway.integrations.web_runtime.runtime import WebProviderRuntime


def _runtime() -> WebProviderRuntime:
    configured = settings(known_model_ids())
    return WebProviderRuntime(
        configured.state_dir,
        browser_executable=configured.web_automation_ungoogled_chromium_executable,
        browser_idle_timeout_seconds=configured.web_automation_browser_idle_timeout_seconds,
        max_concurrent_jobs=configured.web_automation_max_concurrent_jobs,
        per_account_max_concurrent_jobs=configured.web_automation_per_account_max_concurrent_jobs,
        default_timeout_seconds=configured.web_automation_default_timeout_seconds,
        max_retries=configured.web_automation_max_retries,
        cooldown_minutes=configured.web_automation_cooldown_minutes,
        provider_settings=configured.web_provider_settings,
    )


async def _run(args: argparse.Namespace) -> None:
    runtime = _runtime()
    await runtime.startup()
    try:
        if args.action == "add":
            account = runtime.add_account(args.provider, args.email)
            print(f"Added {account.email} for {args.provider}; run login next.")
        elif args.action == "login":
            print(f"Complete the login in the opened browser for {args.email}.")
            await runtime.login(args.provider, args.email)
            print(f"Saved browser session for {args.email}.")
        else:
            for account in runtime.list_accounts(args.provider):
                print(f"{account.email}\t{account.status}")
    finally:
        await runtime.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage ai-web-provider browser accounts.")
    subcommands = parser.add_subparsers(dest="action", required=True)
    for action in ("add", "login"):
        command = subcommands.add_parser(action)
        command.add_argument("--provider", choices=("perplexity", "google_flow"), required=True)
        command.add_argument("--email", required=True)
    command = subcommands.add_parser("list")
    command.add_argument("--provider", choices=("perplexity", "google_flow"), required=True)
    asyncio.run(_run(parser.parse_args()))
