from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol


@dataclass(frozen=True)
class ResolvedModel:
    id: str
    provider: str
    mode: str
    provider_model: str | None


@dataclass(frozen=True)
class TextToTextRequest:
    messages: list[dict[str, Any]]
    model: ResolvedModel


@dataclass
class TextToTextResult:
    text: str
    provider_state: dict[str, Any] | None = None


class TextToTextProvider(Protocol):
    async def complete(
        self, request: TextToTextRequest, provider_state: dict[str, Any] | None
    ) -> TextToTextResult: ...

    async def stream(
        self, request: TextToTextRequest, provider_state: dict[str, Any] | None
    ) -> AsyncIterator[TextToTextResult]: ...
