from typing import AsyncIterator

from ai_web_provider import TaskKind, TaskRequest

from ai_provider_gateway.domain.text_to_text import TextToTextRequest, TextToTextResult
from ai_provider_gateway.integrations.web_runtime.runtime import WebProviderRuntime


class WebPerplexityTextToTextAdapter:
    def __init__(self, runtime: WebProviderRuntime, timeout: float) -> None:
        self._runtime = runtime
        self._timeout = timeout

    async def complete(self, request: TextToTextRequest, provider_state: dict | None) -> TextToTextResult:
        prompt = "\n\n".join(
            message["content"] if isinstance(message["content"], str) else "".join(item["text"] for item in message["content"])
            for message in request.messages
            if message.get("role") in {"system", "user"}
        )
        result = await self._runtime.dispatcher.execute(TaskRequest(
            provider="perplexity", kind=TaskKind.TEXT, prompt=prompt, count=1, timeout=self._timeout,
            params={"model": request.model.provider_model},
            workspace_ref=(provider_state or {}).get("workspace_ref"),
        ))
        text = next((artifact.text for artifact in result.artifacts if artifact.text), "")
        return TextToTextResult(text, {"workspace_ref": result.workspace_ref} if result.workspace_ref else None)

    async def stream(self, request: TextToTextRequest, provider_state: dict | None) -> AsyncIterator[TextToTextResult]:
        yield await self.complete(request, provider_state)
