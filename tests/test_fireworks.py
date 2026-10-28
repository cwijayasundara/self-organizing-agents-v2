"""Fireworks routing, family identity and reported-usage accounting contracts."""
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

from agora_v2.budget import AccountingError
from agora_v2.models import ModelRequest
from agora_v2.models.live import LiveModel, model_price, validate_live_config


def configuration():
    return {
        'models': {
            'glm': {'provider': 'fireworks', 'id': 'accounts/fireworks/models/glm-5p3-flash',
                    'family': 'glm', 'key_env': 'FIREWORKS_API_KEY',
                    'input_micro_per_token': .15, 'cached_input_micro_per_token': .03,
                    'output_micro_per_token': .5},
            'deepseek': {'provider': 'fireworks', 'id': 'accounts/fireworks/models/deepseek-v4p1-flash-1017',
                         'family': 'deepseek', 'key_env': 'FIREWORKS_API_KEY',
                         'input_micro_per_token': .3, 'cached_input_micro_per_token': .006,
                         'output_micro_per_token': 1.2},
            'minimax': {'provider': 'fireworks', 'id': 'accounts/fireworks/models/minimax-m3p1-flash',
                        'family': 'minimax', 'key_env': 'FIREWORKS_API_KEY',
                        'input_micro_per_token': .15, 'cached_input_micro_per_token': .015,
                        'output_micro_per_token': .6},
        },
        'bootstrap': ['glm', 'deepseek', 'minimax'], 'checker': 'deepseek', 'leaf': 'deepseek',
    }


def test_fireworks_accepts_distinct_model_families_on_one_provider():
    config = configuration()
    assert validate_live_config(config, 1)['bootstrap'] == ['glm', 'deepseek', 'minimax']
    assert model_price(config['models']['glm']).cost(100, 20, 40) == 21
    assert model_price(config['models']['deepseek']).cost(100, 20, 40) == 43
    assert model_price(config['models']['minimax']).cost(100, 20, 40) == 22


@pytest.mark.parametrize('change', ['forged_family', 'unknown_model', 'wrong_tariff', 'arbitrary_host'])
def test_fireworks_rejects_unverified_model_configuration(change):
    config = deepcopy(configuration())
    spec = config['models']['glm']
    if change == 'forged_family': spec['family'] = 'deepseek'
    elif change == 'unknown_model': spec['id'] = 'accounts/other/models/glm-5p3-flash'
    elif change == 'wrong_tariff': spec['output_micro_per_token'] = .01
    else: spec['base_url'] = 'https://attacker.invalid'
    with pytest.raises(ValueError):
        validate_live_config(config, 1)


@pytest.mark.parametrize('family', ['glm', 'deepseek', 'minimax'])
async def test_fireworks_routes_bounded_tool_requests_and_counts_all_completion_tokens(monkeypatch, family):
    monkeypatch.setenv('FIREWORKS_API_KEY', 'fireworks-test-secret')
    spec = configuration()['models'][family]
    tool = {'type': 'function', 'function': {'name': 'claim', 'parameters': {'type': 'object'}}}
    messages = ({'role': 'system', 'content': 'protocol'}, {'role': 'user', 'content': 'claim'})
    call = {'id': 'tool-1', 'type': 'function', 'function': {'name': 'claim', 'arguments': '{}'}}
    def handler(request):
        assert str(request.url) == 'https://api.fireworks.ai/inference/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer fireworks-test-secret'
        body = json.loads(request.content)
        assert body['model'] == spec['id']
        assert body['max_tokens'] == 200 and body['stream'] is False
        assert body['service_tier'] == 'default'
        assert body['reasoning_effort'] == ('low' if family in ('glm', 'minimax') else 'none')
        assert 'thinking' not in body
        assert body['messages'] == list(messages) and body['tools'] == [tool]
        return httpx.Response(200, json={
            'id': 'fw-response', 'choices': [{'message': {'content': None, 'tool_calls': [call]}, 'finish_reason': 'tool_calls'}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                      'prompt_tokens_details': {'cached_tokens': 40},
                      'completion_tokens_details': {'reasoning_tokens': 12}},
        })
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await LiveModel(spec, client).complete(ModelRequest(family, 'envelope', 200, messages, (tool,)))
    assert (response.input_tokens, response.output_tokens, response.cached_input_tokens) == (100, 20, 40)
    assert response.content == '' and response.tool_calls == (call,)
    assert response.finish_reason == 'tool_calls' and response.request_id == 'fw-response'


@pytest.mark.parametrize('usage', [None, {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                                        'prompt_tokens_details': {'cached_tokens': 101}}])
async def test_fireworks_missing_or_invalid_usage_fails_accounting(monkeypatch, usage):
    monkeypatch.setenv('FIREWORKS_API_KEY', 'fireworks-test-secret')
    data = {'id': 'fw-response', 'choices': [{'message': {'content': 'answer'}, 'finish_reason': 'stop'}], 'usage': usage}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data))) as client:
        with pytest.raises(AccountingError):
            await LiveModel(configuration()['models']['deepseek'], client).complete(ModelRequest('deepseek', 'question', 200))


async def test_fireworks_http_errors_do_not_retry_or_expose_keys(monkeypatch):
    monkeypatch.setenv('FIREWORKS_API_KEY', 'fireworks-test-secret')
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(429, json={'error': 'fireworks-test-secret'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError) as exc:
            await LiveModel(configuration()['models']['glm'], client).complete(ModelRequest('glm', 'question', 200))
    assert len(requests) == 1 and 'fireworks-test-secret' not in str(exc.value)


def test_example_configuration_runs_both_families_using_only_fireworks_key(monkeypatch):
    monkeypatch.setenv('FIREWORKS_API_KEY', 'fireworks-test-secret')
    monkeypatch.delenv('GLM_API_KEY', raising=False)
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    path = Path(__file__).resolve().parents[1] / 'examples/models.example.json'
    config = validate_live_config(json.loads(path.read_text()), 1)
    models = [LiveModel(spec) for spec in config['models'].values()]
    assert {model.provider for model in models} == {'fireworks'}
    assert {config['models'][key]['family'] for key in config['bootstrap']} == {'glm', 'deepseek', 'minimax'}


@pytest.mark.parametrize('direct,verified_date', [(False, '2026-10-28'), (True, '2026-10-27')])
async def test_runtime_records_verification_date_for_the_selected_provider(tmp_path, direct, verified_date):
    from agora_v2.live import build_live_runtime
    from agora_v2.mission import load_mission
    from agora_v2.models import ScriptedModel

    config = configuration()
    if direct:
        for family, model_id in [('glm', 'glm-5.3-flash'), ('deepseek', 'deepseek-flash')]:
            config['models'][family].update(provider=family, id=model_id)
    async def verify(image):
        return {'image': image, 'revision': 'test-preflight'}
    mission = load_mission(Path(__file__).resolve().parents[1] / 'examples/evidence_review/mission.json')
    runtime = await build_live_runtime(mission, config, 1, tmp_path / 'run',
                                       models={k: ScriptedModel([]) for k in config['models']}, image_verifier=verify)
    try:
        assert runtime.model_config['price_verified_date'] == verified_date
    finally:
        await runtime.dispatcher.executor.close()
        runtime.ledger.close()
