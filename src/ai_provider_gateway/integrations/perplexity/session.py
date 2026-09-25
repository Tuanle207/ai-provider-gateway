import argparse
import json
import time
from pathlib import Path


def session_path(state_dir: Path | None = None) -> Path:
    root = state_dir or Path.home() / ".local" / "state" / "ai-provider-gateway"
    return root / "perplexity-session.json"


def load_session(state_dir: Path | None = None) -> dict[str, str] | None:
    path = session_path(state_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_session(cookies: dict[str, str], state_dir: Path | None = None) -> None:
    path = session_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies), encoding="utf-8")


def interactive_login(timeout: float = 600.0, state_dir: Path | None = None) -> dict[str, str]:
    try:
        from patchright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("Install the driver extra to use interactive login.") from error
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        context.new_page().goto("https://www.perplexity.ai/")
        deadline = time.monotonic() + timeout
        cookies: dict[str, str] = {}
        while time.monotonic() < deadline:
            cookies = {cookie["name"]: cookie["value"] for cookie in context.cookies()}
            if any("session-token" in name for name in cookies):
                browser.close()
                save_session(cookies, state_dir)
                return cookies
            time.sleep(1)
        browser.close()
    raise RuntimeError("No Perplexity session cookie was captured before timeout.")


def main() -> None:
    from ai_provider_gateway.config import settings
    from ai_provider_gateway.integrations.registry import known_model_ids

    parser = argparse.ArgumentParser(description="Sign in to Perplexity and save session cookies.")
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()
    configured = settings(known_model_ids())
    interactive_login(args.timeout, configured.state_dir)
    print(f"Session saved to {session_path(configured.state_dir)}")
