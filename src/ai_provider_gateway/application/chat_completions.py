from typing import AsyncIterator

from ai_provider_gateway.domain.text_to_text import ResolvedModel, TextToTextProvider, TextToTextRequest, TextToTextResult
from ai_provider_gateway.infrastructure.conversation_store import ConversationStore


class ChatCompletions:
    def __init__(self, providers: dict[str, TextToTextProvider], store: ConversationStore) -> None:
        self._providers = providers
        self._store = store

    @staticmethod
    def _key(model: ResolvedModel, conversation_id: str) -> str:
        return f"{model.provider}:{model.id}:{conversation_id}"

    async def complete(
        self, messages: list[dict], model: ResolvedModel, conversation_id: str | None
    ) -> TextToTextResult:
        state = await self._store.get(self._key(model, conversation_id)) if conversation_id else None
        result = await self._provider(model).complete(TextToTextRequest(messages, model), state)
        if conversation_id and result.provider_state:
            await self._store.set(self._key(model, conversation_id), result.provider_state)
        return result

    async def stream(
        self, messages: list[dict], model: ResolvedModel, conversation_id: str | None
    ) -> AsyncIterator[TextToTextResult]:
        state = await self._store.get(self._key(model, conversation_id)) if conversation_id else None
        last: TextToTextResult | None = None
        async for result in self._provider(model).stream(TextToTextRequest(messages, model), state):
            last = result
            yield result
        if conversation_id and last and last.provider_state:
            await self._store.set(self._key(model, conversation_id), last.provider_state)

    def _provider(self, model: ResolvedModel) -> TextToTextProvider:
        try:
            return self._providers[model.provider]
        except KeyError:
            raise LookupError(f"No chat provider is configured for `{model.provider}`.") from None
