import hashlib
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Artifact:
    id: str
    path: Path
    mime_type: str
    size: int
    sha256: str


class ArtifactStore:
    def __init__(self, output_root: Path) -> None:
        self._root = output_root.resolve()
        self._artifacts: dict[str, Artifact] = {}

    def register(self, provider_path: Path, mime_type: str | None = None) -> Artifact:
        path = provider_path.resolve()
        try:
            path.relative_to(self._root)
        except ValueError as error:
            raise ValueError("Provider artifact path is outside the configured output directory.") from error
        if not path.is_file():
            raise ValueError("Provider artifact does not exist.")
        contents = path.read_bytes()
        artifact = Artifact(
            id=f"artifact-{uuid.uuid4().hex}",
            path=path,
            mime_type=mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            size=len(contents),
            sha256=hashlib.sha256(contents).hexdigest(),
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)
