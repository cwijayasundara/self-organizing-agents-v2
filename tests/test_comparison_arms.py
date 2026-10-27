from pathlib import Path
import json
import pytest
from agora_v2.eval.execution import execute_arm
from agora_v2.models import ModelResponse, ScriptedModel
from agora_v2.mission import load_mission

ROOT=Path(__file__).resolve().parents[1]


def memo():
    steps=json.loads((ROOT/'examples/evidence_review/replay.json').read_text())
    return next(s['action']['content'] for s in steps if s['action'].get('type')=='publish' and s['action'].get('task_id')=='$task:final')


async def test_plain_single_has_real_tool_turns_and_independent_judging(tmp_path):
    config=json.loads((ROOT/'examples/models.example.json').read_text())
    responses=[ModelResponse('{"type":"read_evidence","ref":"README.md"}',10,10,'read'),ModelResponse(json.dumps({'type':'final','content':memo()}),20,200,'final')]
    judge=ModelResponse(json.dumps({'covered':[True]*5,'unsupported_claims':[],'issues':[]}),20,20,'judge')
    models={'glm':ScriptedModel(responses),'deepseek':ScriptedModel([judge])}
    result=await execute_arm('plain_single',load_mission(ROOT/'examples/evidence_review/mission.json'),config,1,tmp_path/'run',seed=7,models=models)
    assert result.status=='completed' and result.metrics['model_calls']==3
    assert result.metrics['unsupported_claims']==[]
    assert result.metadata['seed']==7
    trace=json.loads((tmp_path/'run/trace.json').read_text())
    assert len(trace['peers'])==1
    assert any(e['type']=='tool_executed' for e in trace['events'])
    assert trace['mode']=='offline_fake'


async def test_plain_single_without_judge_does_not_claim_completion(tmp_path):
    config=json.loads((ROOT/'examples/models.example.json').read_text())
    models={'glm':ScriptedModel([ModelResponse(json.dumps({'type':'final','content':memo()}),10,100,'final')]),'deepseek':ScriptedModel([ModelResponse('not-json',10,10,'judge')])}
    result=await execute_arm('plain_single',load_mission(ROOT/'examples/evidence_review/mission.json'),config,1,tmp_path/'run',models=models)
    assert result.status!='completed'
    assert result.metrics['execution_errors']>0 or result.metadata['issues']


@pytest.mark.sandbox
async def test_external_context_rejects_semantic_subcalls(tmp_path):
    config=json.loads((ROOT/'examples/models.example.json').read_text())
    class Solver:
        async def complete(self,request):
            data=json.loads(request.prompt)
            if not data['feedback']:
                action={'type':'open_evidence','ref':'cost_model.csv'}
            elif 'handle' in data['feedback']:
                action={'type':'execute','code':"semantic_call('deepseek',[],'escape',10)", 'handles':[data['feedback']['handle']]}
            else:
                action={'type':'final','content':memo()}
            return ModelResponse(json.dumps(action),10,100,'solver')
    judge=ModelResponse(json.dumps({'covered':[True]*5,'unsupported_claims':[],'issues':[]}),20,20,'judge')
    result=await execute_arm('external_context',load_mission(ROOT/'examples/evidence_review/mission.json'),config,1,tmp_path/'run',models={'glm':Solver(),'deepseek':ScriptedModel([judge])})
    trace=json.loads((tmp_path/'run/trace.json').read_text())
    assert not any(e['type']=='semantic_call_started' for e in trace['events'])
    assert any(e['type']=='action_rejected' for e in trace['events'])


@pytest.mark.sandbox
async def test_single_root_rlm_executes_author_recursion_and_independent_judge(tmp_path):
    config=json.loads((ROOT/'examples/models.example.json').read_text())
    code="```repl\ncheck=llm_query(context['evidence']['cost_model.csv'],model='leaf')\nanswer['content']="+repr(memo())+"\nanswer['ready']=True\n```"
    judge=ModelResponse(json.dumps({'covered':[True]*5,'unsupported_claims':[],'issues':[]}),20,20,'judge')
    result=await execute_arm('single_root_rlm',load_mission(ROOT/'examples/evidence_review/mission.json'),config,1,tmp_path/'run',models={'glm':ScriptedModel([ModelResponse(code,10,500,'root')]),'deepseek':ScriptedModel([ModelResponse('507000',10,10,'leaf'),judge])})
    assert result.status=='completed' and result.metrics['model_calls']==3
    assert result.metrics['unsupported_claims']==[]
    trace=json.loads((tmp_path/'run/trace.json').read_text())
    assert len(trace['peers'])==1
    assert any(e['type']=='semantic_call_started' for e in trace['events'])


async def test_arm_cleanup_failure_preserves_failed_trace(tmp_path,monkeypatch):
    import agora_v2.eval.execution as execution
    async def verify():return {}
    class BrokenCleanup:
        def __init__(self,*args,**kwargs):pass
        async def close(self):raise RuntimeError('cleanup unavailable')
    monkeypatch.setattr(execution,'verify_author_image',verify)
    monkeypatch.setattr(execution,'DockerExecutor',BrokenCleanup)
    config=json.loads((ROOT/'examples/models.example.json').read_text())
    judge=ModelResponse(json.dumps({'covered':[True]*5,'unsupported_claims':[],'issues':[]}),20,20,'judge')
    result=await execute_arm('external_context',load_mission(ROOT/'examples/evidence_review/mission.json'),config,1,tmp_path/'run',models={'glm':ScriptedModel([ModelResponse(json.dumps({'type':'final','content':memo()}),10,100,'final')]),'deepseek':ScriptedModel([judge])})
    assert result.status=='failed'
    assert json.loads((tmp_path/'run/trace.json').read_text())['status']=='failed'
