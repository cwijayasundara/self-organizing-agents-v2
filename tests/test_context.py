import pytest
from agora_v2.context import ContextStore


def test_external_context_bounds_and_citation_preservation(tmp_path):
    store=ContextStore(tmp_path/'context')
    handle=store.put('x'*20000,('README.md',))
    preview=store.preview(handle,100)
    assert preview.text=='x'*100 and preview.truncated
    assert preview.evidence==('README.md',)
    sliced=store.slice(handle,100,20)
    assert store.preview(sliced,100).text=='x'*20
    assert store.preview(sliced,100).evidence==('README.md',)
    with pytest.raises(ValueError):
        store.preview('../gold.json',100)
    with pytest.raises(ValueError):
        store.preview(handle,10001)
    with pytest.raises(ValueError):
        store.slice(handle,-1,2)


def test_peer_snapshot_contains_bounded_artifact_preview(tmp_path):
    from agora_v2.ledger import Ledger,TaskSpec
    from agora_v2.trace import peer_snapshot
    with Ledger(tmp_path/'db') as l:
        l.register_peer('p','family')
        t=l.propose_task(TaskSpec('large','analyze',{},(),('review',)))
        artifact=l.publish(l.claim(t.id,'p',30).claim,'x'*20000,[])
        data=peer_snapshot(l)
        record=data['artifacts'][0]
        assert record['id']==artifact.id
        assert len(record['content'])<=1000
        assert record['content_truncated'] is True
