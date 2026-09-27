from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ai_provider_gateway.domain.text_to_text import ResolvedModel


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    n: int
    aspect_ratio: str
    model: ResolvedModel


@dataclass(frozen=True)
class GeneratedImage:
    path: Path
    mime_type: str


class ImageGenerationProvider(Protocol):
    async def generate(self, request: ImageGenerationRequest) -> list[GeneratedImage]: ...
