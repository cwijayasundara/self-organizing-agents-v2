import pytest
from agora_v2.ledger import Ledger, TaskSpec


def spec(key, final=False):
    return TaskSpec(key, 'review', {}, (), ('checked',), final=final)


def test_scope_review_final_dependencies_and_stale_completion(tmp_path):
    with Ledger(tmp_path/'db') as ledger:
        ledger.register_peer('a', 'one')
        ledger.register_peer('b', 'two')
        final = ledger.propose_task(spec('final', True))
        cost = ledger.propose_task(spec('cost'))
        assert not ledger.claim(final.id, 'a', 30).ok
        proposal = ledger.propose_scope('a', [cost.id], 0)
        with pytest.raises(ValueError):
            ledger.review_scope(proposal, 'a', True, 'self')
        assert ledger.review_scope(proposal, 'b', True, 'needed') == 1
        assert not ledger.claim(final.id, 'a', 30).ok
        a = ledger.publish(ledger.claim(cost.id, 'a', 30).claim, 'cost [README.md]', ['README.md'])
        ledger.review_artifact(a.id, 'b', True, 'checked')
        a = ledger.publish(ledger.claim(final.id, 'b', 30).claim, 'memo [README.md]', ['README.md'])
        ledger.review_artifact(a.id, 'a', True, 'checked')
        snapshot = ledger.completion_snapshot()
        assert snapshot.scope_version == 1
        assert len(snapshot.artifact_ids) == 2
        optional = ledger.propose_task(spec('optional'))
        assert ledger.snapshot_current(snapshot)
        change = ledger.propose_scope('b', [cost.id, optional.id], 1)
        assert not ledger.snapshot_current(snapshot)
        ledger.review_scope(change, 'a', True, 'critical')
        assert not ledger.snapshot_current(snapshot)
        assert ledger.completion_snapshot() is None


def test_rejected_critical_scope_cannot_disappear(tmp_path):
    with Ledger(tmp_path/'db') as ledger:
        ledger.register_peer('a','one')
        ledger.register_peer('b','two')
        ledger.propose_task(spec('final', True))
        required = ledger.propose_task(spec('needed'))
        initial = ledger.propose_scope('a', [required.id], 0)
        ledger.review_scope(initial, 'b', False, 'insufficient scope')
        assert ledger.unresolved_scope()
        with pytest.raises(ValueError):
            ledger.propose_scope('a', [], 0)
        replacement = ledger.propose_scope('a', [required.id], 0)
        ledger.review_scope(replacement, 'b', True, 'now justified')
        assert not ledger.unresolved_scope()
        with pytest.raises(ValueError):
            ledger.propose_scope('a', [required.id], 0)


def test_scope_amendment_cannot_reapprove_final_from_previous_version(tmp_path):
    with Ledger(tmp_path/'db') as ledger:
        for p in ['a','b','c']:
            ledger.register_peer(p,p)
        final=ledger.propose_task(spec('final',True))
        task=ledger.propose_task(spec('cost'))
        proposal=ledger.propose_scope('a',[task.id],0)
        ledger.review_scope(proposal,'b',True,'approved')
        artifact=ledger.publish(ledger.claim(task.id,'a',30).claim,'cost',[])
        ledger.review_artifact(artifact.id,'b',True,'checked')
        old=ledger.publish(ledger.claim(final.id,'a',30).claim,'old memo',[])
        ledger.review_artifact(old.id,'b',True,'checked')
        change=ledger.propose_scope('b',[task.id],1)
        ledger.review_scope(change,'c',True,'new critical scope revision')
        with pytest.raises(ValueError,match='stale|published'):
            ledger.review_artifact(old.id,'c',True,'reapprove old')
        assert ledger.completion_snapshot() is None
