from ai_provider_gateway.domain.image_generation import GeneratedImage, ImageGenerationProvider, ImageGenerationRequest


class ImageGenerations:
    def __init__(self, providers: dict[str, ImageGenerationProvider]) -> None:
        self._providers = providers

    async def generate(self, request: ImageGenerationRequest) -> list[GeneratedImage]:
        provider = self._providers.get(request.model.provider)
        if provider is None:
            raise LookupError(f"No image provider is configured for `{request.model.provider}`.")
        return await provider.generate(request)
