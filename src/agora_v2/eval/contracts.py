from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvaluationInput:
    brief: str
    rubric: tuple[str,...]
    manifest: Path
    limits: dict
    seed: int


@dataclass(frozen=True)
class ArmResult:
    arm: str
    status: str
    memo: str
    metrics: dict
    mode: str
    metadata: dict
