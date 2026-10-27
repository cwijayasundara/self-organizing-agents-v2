from dataclasses import dataclass, field
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Limits:
    budget_usd: float = 1.0
    wall_seconds: float = 480
    model_calls: int = 40
    bootstrap_peers: int = 3
    active_contexts: int = 5
    total_identities: int = 8
    semantic_depth: int = 1
    repair_attempts: int = 2

    def __post_init__(self):
        for name in ('budget_usd', 'wall_seconds'):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'invalid {name}')
        for name in ('model_calls', 'bootstrap_peers', 'active_contexts', 'total_identities'):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f'invalid {name}')
        if not 0 <= self.semantic_depth <= 1 or not 0 <= self.repair_attempts <= 2:
            raise ValueError('depth/repair policy exceeded')
        if self.bootstrap_peers > self.active_contexts or self.active_contexts > self.total_identities:
            raise ValueError('inconsistent membership limits')


@dataclass(frozen=True)
class Mission:
    brief: str
    rubric: tuple[str, ...]
    manifest: Path
    limits: Limits = field(default_factory=Limits)


def load_mission(path: Path) -> Mission:
    path = Path(path).resolve()
    obj = json.loads(path.read_text())
    return Mission((path.parent / obj['brief']).read_text(), tuple(obj['rubric']),
                   (path.parent / obj['manifest']).resolve(), Limits(**obj.get('limits', {})))
