import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from agora_v2.mission import Limits, load_mission
from agora_v2.evidence import EvidenceStore

FIXTURE = Path(__file__).resolve().parents[1] / "examples/evidence_review"


def test_mission_is_immutable_and_evidence_has_no_gold():
    mission = load_mission(FIXTURE / "mission.json")
    assert mission.limits.budget_usd == 1
    assert mission.limits.active_contexts == 5
    assert len(EvidenceStore(mission.manifest).metadata()) == 9
    assert "gold" not in str(EvidenceStore(mission.manifest).metadata())
    assert "450 words" in mission.brief
    with pytest.raises(dataclasses.FrozenInstanceError):
        mission.brief = "replace"


@pytest.mark.parametrize("kwargs", [{"budget_usd": 0}, {"model_calls": -1}, {"active_contexts": 0}, {"semantic_depth": 2}, {"repair_attempts": 3}, {"wall_seconds": float('nan')}])
def test_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        Limits(**kwargs)


def test_bounded_reads_and_unlisted_paths():
    store = EvidenceStore(FIXTURE / "manifest.json")
    assert store.read("README.md", 0, 5) == "# Cor"
    for ref in ["../gold.json", "/etc/passwd", "gold.json", "studies/../../brief.md"]:
        with pytest.raises(ValueError):
            store.read(ref, 0, 10)
    for start, length in [(-1, 1), (0, 10001), (0, -1)]:
        with pytest.raises(ValueError):
            store.read("README.md", start, length)


def test_hash_and_symlink_escape(tmp_path):
    root = tmp_path / "sources"
    root.mkdir()
    evidence = root / "a.txt"
    evidence.write_text("safe")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"root": "sources", "files": {"a.txt": hashlib.sha256(b"safe").hexdigest()}}))
    store = EvidenceStore(manifest)
    evidence.write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        store.read("a.txt", 0, 10)
    evidence.unlink()
    outside = tmp_path / "secret"
    outside.write_text("safe")
    evidence.symlink_to(outside)
    with pytest.raises(ValueError):
        store.read("a.txt", 0, 10)
