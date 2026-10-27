from dataclasses import dataclass
import json
from pathlib import Path
import re
import uuid


@dataclass(frozen=True)
class Preview:
    text: str
    truncated: bool
    evidence: tuple[str, ...]


class ContextStore:
    def __init__(self, root: Path):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.records={}

    def put(self, value: str, evidence=()) -> str:
        if not isinstance(value,str) or len(value.encode())>1000000:
            raise ValueError('context must be bounded text')
        ident=uuid.uuid4().hex
        self.records[ident]=tuple(evidence)
        (self.root/ident).write_text(value)
        return ident

    def get(self, handle: str) -> tuple[str,tuple[str,...]]:
        if not isinstance(handle,str) or not re.fullmatch('[0-9a-f]{32}',handle) or handle not in self.records:
            raise ValueError('unknown context handle')
        path=self.root/handle
        if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('context path escape')
        return path.read_text(),self.records[handle]

    def preview(self, handle: str, max_chars: int=1000) -> Preview:
        if type(max_chars) is not int or not 0<=max_chars<=10000:
            raise ValueError('invalid preview bound')
        value,evidence=self.get(handle)
        return Preview(value[:max_chars],len(value)>max_chars,evidence)

    def slice(self, handle: str, start: int, length: int) -> str:
        if type(start) is not int or type(length) is not int or start<0 or not 0<=length<=1000000:
            raise ValueError('invalid slice')
        value,evidence=self.get(handle)
        return self.put(value[start:start+length],evidence)
