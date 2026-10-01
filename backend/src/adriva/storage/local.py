import hashlib
import os
import tempfile
from pathlib import Path
from typing import Protocol
from uuid import UUID


class ArtifactStore(Protocol):
    def put(self, project_id: UUID, data: bytes) -> tuple[str, str]: ...
    def read(self, key: str, expected_hash: str) -> bytes: ...


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, project_id: UUID, data: bytes) -> tuple[str, str]:
        checksum = hashlib.sha256(data).hexdigest()
        key = f"{project_id}/{checksum}.json"
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temp:
            temp.write(data)
            temporary = Path(temp.name)
        try:
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return checksum, key

    def read(self, key: str, expected_hash: str) -> bytes:
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Invalid artifact key")
        data = target.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise ValueError("Artifact checksum mismatch")
        return data
