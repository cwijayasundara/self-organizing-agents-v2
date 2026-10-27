from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    key: str
    family: str
    capabilities: tuple[str, ...]
