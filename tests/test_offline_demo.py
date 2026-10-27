import json
from pathlib import Path
from agora_v2.demo import replay


async def test_scripted_demo_runs_real_transitions_and_exports(tmp_path):
    result=await replay(tmp_path/'run')
    assert result.status=='completed'
    trace=json.loads((tmp_path/'run'/'trace.json').read_text())
    assert trace['mode']=='scripted'
    events=trace['events']
    assert len([e for e in events if e['type']=='peer_joined'])==4
    assert len([e for e in events if e['type']=='peer_retired'])>=1
    assert any(e['type']=='finding_published' for e in events)
    assert trace['cost']['calls']<=40
    assert all(t['holder'] is None for t in trace['tasks'])
    assert 'RESEARCH_SUMMARY' in trace['final_memo']
    assert not any('gold' in str(c) for c in trace['calls'])
    assert trace['context_objects']>0
