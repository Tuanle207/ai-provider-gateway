import json
import os
from typing import AsyncIterator

from ai_provider_gateway.domain.text_to_text import TextToTextRequest, TextToTextResult
from ai_provider_gateway.integrations.perplexity.model_overrides import apply_model_overrides
from ai_provider_gateway.integrations.perplexity.normalize import answer_from_response
from ai_provider_gateway.integrations.perplexity.session import load_session


class PerplexityTextToTextAdapter:
    """Gateway boundary around the vendored upstream async client."""

    def __init__(self) -> None:
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from perplexity_async import Client

            apply_model_overrides()
            cookies_env = os.environ.get("PERPLEXITY_COOKIES")
            cookies = json.loads(cookies_env) if cookies_env else load_session()
            self._client = await Client(cookies=cookies)
        return self._client

    @staticmethod
    def _query(messages: list[dict]) -> str:
        parts = [
            str(message.get("content", ""))
            for message in messages
            if message.get("role") in {"system", "user"} and message.get("content")
        ]
        return "\n\n".join(parts)

    async def complete(
        self, request: TextToTextRequest, provider_state: dict | None
    ) -> TextToTextResult:
        client = await self._get_client()
        response = await client.search(
            self._query(request.messages),
            mode=request.model.mode,
            model=request.model.provider_model,
            follow_up=provider_state,
        )
        return TextToTextResult(answer_from_response(response), response if isinstance(response, dict) else None)

    async def stream(
        self, request: TextToTextRequest, provider_state: dict | None
    ) -> AsyncIterator[TextToTextResult]:
        client = await self._get_client()
        stream = await client.search(
            self._query(request.messages),
            mode=request.model.mode,
            model=request.model.provider_model,
            follow_up=provider_state,
            stream=True,
        )
        async for response in stream:
            yield TextToTextResult(
                answer_from_response(response), response if isinstance(response, dict) else None
            )
