import hashlib
import json
from pathlib import Path
import subprocess
import pytest
from agora_v2.evidence import EvidenceStore
from agora_v2.eval.frozen_v1 import _revision,materialize_evidence


async def test_frozen_revision_rejects_staged_source_edits(tmp_path,monkeypatch):
    import agora_v2.eval.frozen_v1 as frozen
    def git(*args):return subprocess.run(['git','-C',str(tmp_path),*args],check=True,capture_output=True,text=True).stdout.strip()
    git('init');git('config','user.email','test@example.invalid');git('config','user.name','Test')
    p=tmp_path/'source.py';p.write_text('original')
    git('add','source.py');git('commit','-m','initial')
    monkeypatch.setattr(frozen,'V1_REVISION',git('rev-parse','HEAD'))
    p.write_text('staged malicious edit');git('add','source.py')
    with pytest.raises(ValueError,match='tracked changes'):
        await _revision(tmp_path)


def test_native_evidence_snapshot_excludes_unlisted_gold_alias(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'safe.txt').write_text('safe')
    gold=tmp_path/'gold.json';gold.write_text('HELDOUT-SENTINEL')
    (source/'extra.json').hardlink_to(gold)
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'root':'source','files':{'safe.txt':hashlib.sha256(b'safe').hexdigest()}}))
    snapshot=materialize_evidence(EvidenceStore(manifest),tmp_path/'native-evidence')
    assert (snapshot/'safe.txt').read_text()=='safe'
    assert not (snapshot/'extra.json').exists()
