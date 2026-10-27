import json
from pathlib import Path
import pytest
from agora_v2.demo import replay
from agora_v2.eval.runner import evaluate
from agora_v2.eval.score import score

ROOT=Path(__file__).resolve().parents[1]


async def test_export_evaluation_scores_without_giving_gold_to_arms(tmp_path):
    await replay(tmp_path/'run')
    trace=tmp_path/'run/trace.json'
    config={'mission':str(ROOT/'examples/evidence_review/mission.json'),'gold':str(ROOT/'eval/gold/evidence_review.json'),'seeds':[0],
            'exports':{'dynamic_swarm':str(trace)}}
    cfg=tmp_path/'evaluation.json'
    cfg.write_text(json.dumps(config))
    report=await evaluate(cfg,tmp_path/'report')
    assert len(report['results'])==5
    scored=next(r for r in report['results'] if r['arm']=='dynamic_swarm')
    assert scored['business_field_correctness']==1
    assert scored['interpretation']=='scripted mechanics only; no live comparison'
    assert scored['unsupported_claims'] is None
    assert all('gold' not in str(r.get('arm_input',{})) for r in report['results'])
    assert len([r for r in report['results'] if r['status']=='not_run'])==4
    assert (tmp_path/'report/report.json').exists()


def test_invalid_numeric_summary_is_not_counted_as_correct(tmp_path):
    from agora_v2.eval.contracts import ArmResult
    result=ArmResult('test','completed','RESEARCH_SUMMARY\n```json\n{"verdict":"pilot_knowledge_teams","retracted_source":"studies/okafor_lind_2024.md","inflated_claim_source":"flexweek_whitepaper.md","harmed_group":"Customer Support","cost_mismatch_eur":true}\n```',{},'imported',{})
    scored=score(result,ROOT/'eval/gold/evidence_review.json',ROOT/'examples/evidence_review/manifest.json')
    assert scored['field_correct']['cost_mismatch_eur'] is False
    assert scored['citation_errors']


def test_nonobject_summary_reports_failure_instead_of_crashing():
    from agora_v2.eval.contracts import ArmResult
    result=ArmResult('test','completed','RESEARCH_SUMMARY\n```json\n[]\n```',{},'imported',{})
    scored=score(result,ROOT/'eval/gold/evidence_review.json',ROOT/'examples/evidence_review/manifest.json')
    assert scored['business_field_correctness']==0
    assert scored['citation_errors']


async def test_gold_is_rejected_under_custom_evidence_root(tmp_path):
    import hashlib
    root=tmp_path/'data'
    root.mkdir()
    gold=root/'answer.json'
    gold.write_text('{}')
    (tmp_path/'brief.md').write_text('brief')
    (tmp_path/'manifest.json').write_text(json.dumps({'root':'data','files':{'answer.json':hashlib.sha256(b'{}').hexdigest()}}))
    (tmp_path/'mission.json').write_text(json.dumps({'brief':'brief.md','manifest':'manifest.json','rubric':['test']}))
    cfg=tmp_path/'config.json'
    cfg.write_text(json.dumps({'mission':'mission.json','gold':'data/answer.json'}))
    with pytest.raises(ValueError,match='gold'):
        await evaluate(cfg,tmp_path/'report')
