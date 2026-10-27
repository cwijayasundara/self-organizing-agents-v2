from pathlib import Path
import json
import pytest
from agora_v2.live import build_live_runtime
from agora_v2.models import ScriptedModel, ModelResponse
from agora_v2.mission import load_mission
from agora_v2.context.author import verify_author_image, AUTHOR_IMAGE

ROOT=Path(__file__).resolve().parents[1]


def configuration():
    return json.loads((ROOT/'examples/models.example.json').read_text())


async def test_live_builder_exposes_observable_non_scripted_runtime(tmp_path):
    async def verify(image):return {'image':image,'revision':'verified-by-test-adapter'}
    mission=load_mission(ROOT/'examples/evidence_review/mission.json')
    config=configuration()
    models={k:ScriptedModel([ModelResponse('{"type":"wait"}',10,10,'id')]*20) for k in config['models']}
    runtime=await build_live_runtime(mission,config,.2,tmp_path/'run',models=models,image_verifier=verify)
    assert runtime.mode=='offline_fake' and runtime.schedule is None
    assert runtime.mission.limits.budget_usd==.2
    assert runtime.reasoner is not None
    assert runtime.ledger.db.execute('SELECT COUNT(*) FROM peers').fetchone()[0]==3
    assert runtime.gateway.models['checker'] is models[config['checker']]
    assert all('gold' not in ref for ref in runtime.evidence.files)
    await runtime.dispatcher.executor.close()
    runtime.ledger.close()


@pytest.mark.sandbox
async def test_author_preflight_rejects_base_image_and_accepts_pinned_engine():
    from agora_v2.models.live import LiveUnavailable
    with pytest.raises(LiveUnavailable):
        await verify_author_image('python:3.12-slim')
    result=await verify_author_image(AUTHOR_IMAGE)
    assert result['revision']=='d04208afbad29ca675ab13478c40ee8bebc84bfe'


@pytest.mark.sandbox
async def test_nonscripted_scheduler_completes_with_real_author_engine_and_fake_providers(tmp_path):
    from agora_v2.demo import ReplayModel
    from agora_v2.models import ModelRequest
    steps=json.loads((ROOT/'examples/evidence_review/replay.json').read_text())
    for step in steps:
        if step['action'].get('model_key')=='two':step['action']['model_key']='deepseek'
    script=ReplayModel(steps)
    class Providers:
        async def complete(self,request):
            if request.messages is None:
                if request.prompt.startswith('{'):
                    return ModelResponse(json.dumps({'covered':[True]*5,'unsupported_claims':[],'issues':[]}),20,20,'fake-check')
                return ModelResponse('checked partition',10,10,'fake-leaf')
            payload=None
            for message in request.messages:
                text=message['content']
                pos=text.find('{"instruction":')
                if pos>=0:
                    payload,_=json.JSONDecoder().raw_decode(text[pos:])
                    break
            assert payload is not None
            if script.steps and script.steps[0]['peer']==payload['snapshot']['identity']:
                response=await script.complete(ModelRequest(request.model_key,json.dumps(payload),2000))
                action=json.loads(response.content)
            else:
                action={'type':'wait'}
            prefix="sample=llm_query(context['evidence']['studies/harlow_2025.md'][:200],model='leaf')\n" if action['type']=='finding' else ''
            code='```repl\n'+prefix+"answer['content']="+repr(json.dumps(action))+"\nanswer['ready']=True\n```"
            return ModelResponse(code,100,500,'fake-root')
    provider=Providers()
    config=configuration()
    runtime=await build_live_runtime(load_mission(ROOT/'examples/evidence_review/mission.json'),config,1,tmp_path/'run',models={k:provider for k in config['models']})
    result=await runtime.run(runtime.mission)
    trace=json.loads((tmp_path/'run/trace.json').read_text())
    assert result.status=='completed', trace['issues']
    assert trace['mode']=='offline_fake'
    assert trace['cost']['calls']<=40
    assert len([e for e in trace['events'] if e['type']=='peer_joined'])==4
    assert any(e['type']=='semantic_call_started' for e in trace['events'])
    assert not runtime.reasoner.containers
    runtime.ledger.close()


async def test_live_claim_survives_a_slow_model_episode(tmp_path):
    from agora_v2.ledger import TaskSpec
    from agora_v2.models import ScriptedModel
    async def verify(image):return {'image':image}
    config=configuration()
    runtime=await build_live_runtime(load_mission(ROOT/'examples/evidence_review/mission.json'),config,1,tmp_path/'run',models={k:ScriptedModel([]) for k in config['models']},image_verifier=verify)
    now=[100.0];runtime.ledger.clock=lambda:now[0]
    task=runtime.ledger.propose_task(TaskSpec('slow','analyze',{},(),('checked',)))
    await runtime.dispatcher.apply('p1',{'type':'claim','task_id':task.id},None)
    now[0]+=40
    async with runtime.slots.enter('peer','p1') as ex:
        result=await runtime.dispatcher.apply('p1',{'type':'publish','task_id':task.id,'content':'checked','evidence':[]},ex)
    assert result['version']==1
    runtime.ledger.close()
