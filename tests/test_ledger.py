from concurrent.futures import ThreadPoolExecutor

import pytest

from agora_v2.ledger import Ledger, TaskSpec


def task(key, deps=(), final=False):
    return TaskSpec(key, 'Assess evidence', {'type': 'string'}, ('README.md',), ('cited',), tuple(deps), final)


def setup(tmp_path, clock=lambda: 100):
    ledger = Ledger(tmp_path / 'run.db', clock=clock)
    ledger.register_peer('a', 'family-a')
    ledger.register_peer('b', 'family-b')
    return ledger


def test_concurrent_deduplication_and_claims(tmp_path):
    db = tmp_path / 'run.db'
    ledger = setup(tmp_path)
    def propose(key):
        with Ledger(db) as other:
            return other.propose_task(task(key)).id
    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(propose, ['  COST   MODEL ', 'cost model']))
    assert ids[0] == ids[1]
    def claim(peer):
        with Ledger(db) as other:
            return other.claim(ids[0], peer, 30)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, ['a', 'b']))
    assert sum(r.ok for r in results) == 1
    loser = next(r for r in results if not r.ok)
    assert loser.holder in ('a', 'b') and loser.expires_at > 0
    ledger.close()


def test_fencing_dependencies_independent_review(tmp_path):
    now = [100]
    ledger = setup(tmp_path, lambda: now[0])
    t = ledger.propose_task(task('cost'))
    dependent = ledger.propose_task(task('memo', (t.id,)))
    assert not ledger.claim(dependent.id, 'a', 30).ok
    old = ledger.claim(t.id, 'a', 10).claim
    now[0] = 111
    new = ledger.claim(t.id, 'b', 30).claim
    with pytest.raises(ValueError, match='stale'):
        ledger.publish(old, 'stale', ['README.md'])
    with pytest.raises(ValueError):
        ledger.release(old)
    artifact = ledger.publish(new, 'checked [README.md]', ['README.md'])
    with pytest.raises(ValueError):
        ledger.review_artifact(artifact.id, 'b', True, 'self')
    assert not ledger.claim(dependent.id, 'a', 30).ok
    ledger.review_artifact(artifact.id, 'a', True, 'checked')
    assert ledger.claim(dependent.id, 'a', 30).ok
    assert any(e['type'] == 'artifact_published' for e in ledger.events())
    ledger.close()


def test_missing_dependencies_and_invalid_actor_are_rejected(tmp_path):
    ledger = setup(tmp_path)
    with pytest.raises(ValueError):
        ledger.propose_task(task('bad', ('missing',)))
    t = ledger.propose_task(task('valid'))
    with pytest.raises(ValueError):
        ledger.claim(t.id, 'unknown', 30)
    with pytest.raises(ValueError):
        ledger.claim(t.id, 'a', -1)
    ledger.close()
