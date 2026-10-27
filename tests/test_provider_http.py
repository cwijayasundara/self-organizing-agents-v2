import asyncio
import json
import pytest
import httpx
from agora_v2.models.live import LiveModel, validate_live_config
from agora_v2.models import ModelRequest
from agora_v2.budget import AccountingError


def config(provider):
    return {'provider':provider,'id':'glm-5.3-flash' if provider=='glm' else 'deepseek-flash','family':provider,'key_env':'TEST_KEY','input_micro_per_token':.15 if provider=='glm' else .3,'cached_input_micro_per_token':.03 if provider=='glm' else .006,'output_micro_per_token':.5 if provider=='glm' else 1.2}


def payload(provider):
    usage={'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}
    if provider=='glm':usage['prompt_tokens_details']={'cached_tokens':40}
    else:usage.update({'prompt_cache_hit_tokens':40,'prompt_cache_miss_tokens':60})
    return {'id':'provider-id','model':config(provider)['id'],'choices':[{'index':0,'message':{'role':'assistant','content':'answer'},'finish_reason':'stop'}],'usage':usage}


@pytest.mark.parametrize('provider',['glm','deepseek'])
async def test_provider_bounds_request_and_parses_reported_cache_usage(monkeypatch,provider):
    monkeypatch.setenv('TEST_KEY','secret-for-test-only')
    def handler(request):
        assert request.headers['authorization']=='Bearer secret-for-test-only'
        body=json.loads(request.content)
        assert body['stream'] is False and body['max_tokens']==200
        assert body['thinking']=={'type':'enabled' if provider=='glm' else 'disabled'}
        if provider=='glm':assert body['reasoning_effort']=='low'
        assert body['messages']==[{'role':'user','content':'question'}]
        assert request.url.host==('api.z.ai' if provider=='glm' else 'api.deepseek.com')
        return httpx.Response(200,json=payload(provider))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        model=LiveModel(config(provider),client=client)
        response=await model.complete(ModelRequest(provider,'question',200))
    assert response.content=='answer' and response.input_tokens==100 and response.output_tokens==20
    assert response.cached_input_tokens==40
    assert response.request_id=='provider-id'


async def test_missing_usage_fails_and_http_error_does_not_retry_or_leak_secret(monkeypatch):
    monkeypatch.setenv('TEST_KEY','private-key-marker')
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(429,json={'error':'private-key-marker'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        model=LiveModel(config('glm'),client=client)
        with pytest.raises(RuntimeError) as exc:
            await model.complete(ModelRequest('glm','question',100))
        assert 'private-key-marker' not in str(exc.value)
    assert len(calls)==1
    data=payload('glm');data.pop('usage')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))) as client:
        with pytest.raises(AccountingError):
            await LiveModel(config('glm'),client=client).complete(ModelRequest('glm','question',100))


async def test_provider_request_cancellation_closes_wait_without_retry(monkeypatch):
    monkeypatch.setenv('TEST_KEY','test')
    entered=asyncio.Event()
    async def handler(request):
        entered.set()
        await asyncio.Event().wait()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        task=asyncio.create_task(LiveModel(config('deepseek'),client=client).complete(ModelRequest('deepseek','question',100)))
        await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task


def test_validated_config_keeps_secrets_out_and_rejects_arbitrary_hosts():
    models={'glm':config('glm'),'deepseek':config('deepseek')}
    valid=validate_live_config({'models':models,'bootstrap':['glm','deepseek','glm']},1)
    assert valid['bootstrap']==['glm','deepseek','glm']
    models['glm']['base_url']='https://attacker.invalid'
    with pytest.raises(ValueError):
        validate_live_config({'models':models,'bootstrap':['glm','deepseek','glm']},1)


async def test_v1_tool_calls_preserve_usage_and_structured_messages(monkeypatch):
    monkeypatch.setenv('TEST_KEY','test')
    tool={'type':'function','function':{'name':'claim_task','description':'claim','parameters':{'type':'object','properties':{}}}}
    data=payload('deepseek')
    data['choices'][0]={'message':{'content':None,'tool_calls':[{'id':'call-1','type':'function','function':{'name':'claim_task','arguments':'{}'}}]},'finish_reason':'tool_calls'}
    def handler(request):
        body=json.loads(request.content)
        assert body['tools']==[tool]
        assert body['messages'][0]['role']=='system'
        return httpx.Response(200,json=data)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        request=ModelRequest('deepseek','bounded envelope',200,messages=({'role':'system','content':'protocol'},{'role':'user','content':'claim'}),tools=(tool,))
        result=await LiveModel(config('deepseek'),client=client).complete(request)
    assert result.finish_reason=='tool_calls' and result.tool_calls[0]['id']=='call-1'
    assert result.input_tokens==100 and result.cached_input_tokens==40
