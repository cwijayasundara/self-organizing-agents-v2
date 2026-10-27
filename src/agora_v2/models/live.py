"""Bounded, non-streaming direct GLM/DeepSeek adapters; credentials stay here."""
import json
import math
import os
import re

import httpx

from .protocol import ModelRequest, ModelResponse, Price
from ..budget import AccountingError

ENDPOINTS = {
    'glm': 'https://api.z.ai/api/paas/v4/chat/completions',
    'deepseek': 'https://api.deepseek.com/chat/completions',
}
# USD / million tokens equals microdollars / token. DeepSeek uses the peak
# upper tariff for budget safety; invoice reconciliation can lower that estimate.
CATALOG = {
    'glm': {'glm-5.3-flash': Price(.15, .50, .03), 'glm-5.3': Price(1.4, 4.4, .26), 'glm-4.7': Price(.6, 2.2, .11)},
    'deepseek': {'deepseek-flash': Price(.3, 1.2, .006), 'deepseek-v4-pro': Price(1.32, 3.96, .044)},
}
PRICE_VERIFIED_DATE = '2026-10-27'


class LiveUnavailable(RuntimeError):
    pass


def model_price(spec):
    try:
        expected = CATALOG[spec['provider']][spec['id']]
    except KeyError:
        raise ValueError('unknown provider or model identifier')
    try:
        supplied = Price(spec['input_micro_per_token'], spec['output_micro_per_token'], spec.get('cached_input_micro_per_token'))
        supplied.cost(1, 1)
    except (KeyError, TypeError, AccountingError):
        raise ValueError('known price required')
    if supplied != expected:
        raise ValueError('configured price must match the verified model tariff including cache rate')
    return supplied


def validate_live_config(config: dict, budget_usd: float | None):
    if type(budget_usd) not in (int, float) or not math.isfinite(budget_usd) or budget_usd <= 0:
        raise ValueError('live mode requires an explicit positive spend cap')
    if not isinstance(config, dict) or set(config) - {'models', 'bootstrap', 'checker', 'leaf', 'note'}:
        raise ValueError('unknown live configuration fields')
    models = config.get('models', {})
    bootstrap = config.get('bootstrap', [])
    if not isinstance(models, dict) or len(bootstrap) != 3 or any(k not in models for k in bootstrap):
        raise ValueError('three allowlisted bootstrap models required')
    if len({models[k].get('family') for k in bootstrap}) < 2:
        raise ValueError('bootstrap must span two model families')
    for key, spec in models.items():
        if not isinstance(spec, dict) or set(spec) - {'provider', 'id', 'family', 'key_env', 'input_micro_per_token', 'cached_input_micro_per_token', 'output_micro_per_token'}:
            raise ValueError('unknown model fields or arbitrary endpoint')
        if spec.get('family') != spec.get('provider'):
            raise ValueError('model family must identify the actual provider family')
        if not re.fullmatch('[A-Z][A-Z0-9_]*', spec.get('key_env', '')):
            raise ValueError('model needs an environment variable name, not a literal key')
        model_price(spec)
    for name in ('checker', 'leaf'):
        if name in config and config[name] not in models:
            raise ValueError(f'unknown {name} model')
    return config


class LiveModel:
    def __init__(self, spec: dict, client: httpx.AsyncClient | None = None):
        self.price = model_price(spec)
        self.spec = dict(spec)
        self.provider = spec['provider']
        self._key = os.environ.get(spec['key_env'])
        if not self._key:
            raise ValueError(f"missing environment variable {spec['key_env']}")
        self.client = client

    async def complete(self, request: ModelRequest) -> ModelResponse:
        messages = list(request.messages) if request.messages is not None else [{'role': 'user', 'content': request.prompt}]
        body = {'model': self.spec['id'], 'messages': messages, 'max_tokens': request.max_output_tokens, 'stream': False}
        if request.tools:
            body['tools']=list(request.tools)
            body['tool_choice']='auto'
        if self.provider == 'glm' and self.spec['id'].startswith('glm-5.3'):
            body.update({'thinking': {'type': 'enabled'}, 'reasoning_effort': 'low'})
        else:
            body['thinking'] = {'type': 'disabled'}
        if self.client is not None:
            return await self._complete(self.client, body)
        async with httpx.AsyncClient(timeout=90, follow_redirects=False, trust_env=False) as client:
            return await self._complete(client, body)

    async def _complete(self, client, body):
        async with client.stream('POST', ENDPOINTS[self.provider], headers={'Authorization': 'Bearer ' + self._key}, json=body) as response:
            if response.status_code != 200:
                # Never echo provider bodies, headers, credentials or automatic retry.
                raise RuntimeError(f'{self.provider} HTTP {response.status_code}; request not retried')
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > 1000000:
                    raise AccountingError('provider response exceeded bound; usage unresolved')
        try:
            data = json.loads(raw)
            usage = data['usage']
            inputs, outputs = usage['prompt_tokens'], usage['completion_tokens']
            if self.provider == 'deepseek':
                cached = usage['prompt_cache_hit_tokens']
                misses = usage['prompt_cache_miss_tokens']
                if type(misses) is not int or misses + cached != inputs:
                    raise ValueError('inconsistent cache usage')
            else:
                cached = usage.get('prompt_tokens_details', {}).get('cached_tokens', 0)
            if any(type(x) is not int or x < 0 for x in (inputs, outputs, cached)) or cached > inputs:
                raise ValueError('invalid usage')
            if type(usage.get('total_tokens')) is not int or usage['total_tokens'] != inputs + outputs:
                raise ValueError('inconsistent total usage')
            choice = data['choices'][0]
            content = choice['message'].get('content') or ''
            if not isinstance(data['id'], str) or not data['id'] or not isinstance(content, str):
                raise ValueError('invalid response envelope')
            return ModelResponse(content, inputs, outputs, data['id'], cached, choice['finish_reason'], tuple(choice['message'].get('tool_calls',[])))
        except (ValueError, TypeError, KeyError, IndexError):
            raise AccountingError('missing or malformed reported provider usage/envelope')
