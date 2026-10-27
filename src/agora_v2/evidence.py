from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class EvidenceMetadata:
    ref: str
    sha256: str
    size: int


class EvidenceStore:
    MAX_READ = 10000

    def __init__(self, manifest: Path):
        manifest = Path(manifest).resolve()
        data = json.loads(manifest.read_text())
        self.root = (manifest.parent / data['root']).resolve()
        self.files = dict(data['files'])
        for ref in self.files:
            self._bytes(ref)

    def _bytes(self, ref: str) -> bytes:
        p = PurePosixPath(ref)
        if ref not in self.files or p.is_absolute() or '..' in p.parts or '\\' in ref:
            raise ValueError('evidence reference is not allowed')
        path = self.root / ref
        if not path.resolve().is_relative_to(self.root) or path.is_symlink():
            raise ValueError('evidence path escapes root')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.files[ref]:
            raise ValueError(f'evidence hash mismatch: {ref}')
        return raw

    def metadata(self) -> list[EvidenceMetadata]:
        return [EvidenceMetadata(ref, digest, len(self._bytes(ref))) for ref, digest in sorted(self.files.items())]

    def read(self, ref: str, start: int = 0, length: int = MAX_READ) -> str:
        if type(start) is not int or type(length) is not int or start < 0 or not 0 <= length <= self.MAX_READ:
            raise ValueError('invalid evidence range')
        return self._bytes(ref).decode('utf-8')[start:start + length]
