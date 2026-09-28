from ai_web_provider import TaskKind, TaskRequest

from ai_provider_gateway.domain.image_generation import GeneratedImage, ImageGenerationRequest
from ai_provider_gateway.integrations.web_runtime.runtime import WebProviderRuntime


class WebGoogleFlowImageAdapter:
    def __init__(self, runtime: WebProviderRuntime, timeout: float) -> None:
        self._runtime = runtime
        self._timeout = timeout

    async def generate(self, request: ImageGenerationRequest) -> list[GeneratedImage]:
        result = await self._runtime.dispatcher.execute(TaskRequest(
            provider="google_flow", kind=TaskKind.IMAGE, prompt=request.prompt, count=request.n,
            timeout=self._timeout,
            params={"model": request.model.provider_model, "aspect_ratio": request.aspect_ratio},
        ))
        return [GeneratedImage(self._runtime.output_dir / artifact.rel_path, artifact.mime) for artifact in result.artifacts if artifact.kind is TaskKind.IMAGE and artifact.rel_path]
