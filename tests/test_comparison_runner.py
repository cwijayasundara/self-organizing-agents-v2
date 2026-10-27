import json
from pathlib import Path
import pytest
from agora_v2.eval.contracts import ArmResult
from agora_v2.eval.runner import evaluate

ROOT=Path(__file__).resolve().parents[1]


async def test_repeated_execution_has_one_total_cap_and_never_passes_gold_to_runner(tmp_path,monkeypatch):
    import agora_v2.eval.runner as runner
    seen=[]
    memo=next(s['action']['content'] for s in json.loads((ROOT/'examples/evidence_review/replay.json').read_text()) if s['action'].get('task_id')=='$task:final' and s['action']['type']=='publish')
    async def execute(arm,mission,models_config,budget_usd,output,**kwargs):
        assert 'gold' not in str(mission.manifest) and 'gold' not in models_config
        seen.append((arm,kwargs['seed'],budget_usd,mission.limits.wall_seconds))
        return ArmResult(arm,'completed',memo,{'settled_micro':1000,'unresolved_micro':0,'model_calls':3,'latency_seconds':.1,'peers':1,'unsupported_claims':[]},'offline_fake',{'seed':kwargs['seed']})
    monkeypatch.setattr(runner,'execute_arm',execute)
    cfg={'mission':str(ROOT/'examples/evidence_review/mission.json'),'gold':str(ROOT/'eval/gold/evidence_review.json'),'models':str(ROOT/'examples/models.example.json'),'execute':['plain_single','external_context','single_root_rlm','dynamic_swarm','frozen_v1'],'seeds':[1,2]}
    path=tmp_path/'config.json';path.write_text(json.dumps(cfg))
    report=await evaluate(path,tmp_path/'report',budget_usd=1)
    assert len(seen)==10 and all(r[2]==.1 for r in seen)
    assert report['budget']['total_cap_usd']==1
    assert report['budget']['settled_micro']==10000
    assert report['aggregate']['plain_single']['runs']==2
    assert (tmp_path/'report/report.md').exists()


async def test_execution_requires_explicit_cap_before_dispatch(tmp_path):
    cfg={'mission':str(ROOT/'examples/evidence_review/mission.json'),'gold':str(ROOT/'eval/gold/evidence_review.json'),'models':str(ROOT/'examples/models.example.json'),'execute':['plain_single']}
    path=tmp_path/'config.json';path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError,match='cap'):
        await evaluate(path,tmp_path/'report')


async def test_inner_overrun_stops_later_dispatches_under_total_cap(tmp_path,monkeypatch):
    import agora_v2.eval.runner as runner
    seen=[]
    async def execute(arm,*args,**kwargs):
        seen.append(arm)
        return ArmResult(arm,'failed','',{'settled_micro':600000,'unresolved_micro':0,'model_calls':1},'offline_fake',{'seed':0})
    monkeypatch.setattr(runner,'execute_arm',execute)
    cfg={'mission':str(ROOT/'examples/evidence_review/mission.json'),'gold':str(ROOT/'eval/gold/evidence_review.json'),'models':str(ROOT/'examples/models.example.json'),'execute':['plain_single','external_context']}
    path=tmp_path/'config.json';path.write_text(json.dumps(cfg))
    report=await evaluate(path,tmp_path/'report',budget_usd=1)
    assert seen==['plain_single']
    assert next(r for r in report['results'] if r['arm']=='external_context')['status']=='budget_exhausted'
    assert report['budget']['settled_micro']==600000
