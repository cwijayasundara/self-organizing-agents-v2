import asyncio
import json
from ..budget import AccountingError


class Gateway:
    MAX_PROMPT_BYTES=100000
    MAX_OUTPUT_TOKENS=8000

    def __init__(self, models, prices, budget):
        self.models, self.prices, self.budget = models, prices, budget

    async def call(self, request, purpose, execution):
        price=self.prices.get(request.model_key)
        if price is None or request.model_key not in self.models:
            raise AccountingError('unknown model or price')
        if execution is None or not execution.held:
            raise ValueError('dispatch requires active execution slot')
        if not isinstance(request.prompt,str) or len(request.prompt.encode())>self.MAX_PROMPT_BYTES or type(request.max_output_tokens) is not int or not 0<request.max_output_tokens<=self.MAX_OUTPUT_TOKENS:
            raise AccountingError('unbounded model request')
        if request.messages is not None:
            if not isinstance(request.messages, (list, tuple)) or not request.messages:
                raise AccountingError('invalid structured model messages')
            for message in request.messages:
                if not isinstance(message, dict) or set(message)-{'role','content','tool_call_id','tool_calls','name'} or message.get('role') not in ('system','user','assistant','tool') or (not isinstance(message.get('content'), str) and not (message.get('role')=='assistant' and message.get('content') is None and message.get('tool_calls'))):
                    raise AccountingError('invalid structured model message')
        if request.tools is not None and (not isinstance(request.tools,(tuple,list)) or len(request.tools)>128 or any(not isinstance(t,dict) or t.get('type')!='function' or not isinstance(t.get('function'),dict) for t in request.tools)):
            raise AccountingError('invalid bounded tool definitions')
        wire=json.dumps({'messages':request.messages,'tools':request.tools},ensure_ascii=False) if request.messages is not None or request.tools is not None else request.prompt
        prompt_bytes = len(wire.encode())
        if prompt_bytes > self.MAX_PROMPT_BYTES:
            raise AccountingError('unbounded structured model prompt')
        # Byte count plus adapter envelope allowance conservatively bounds tokens.
        reserved=price.cost(prompt_bytes+1024,request.max_output_tokens)
        ident=self.budget.reserve(getattr(execution,"billing_identity",execution.identity),purpose,reserved)
        self.budget.submitted(ident)
        try:
            response=await self.models[request.model_key].complete(request)
            usage=(response.input_tokens,response.output_tokens)
            if any(type(x) is not int or x<0 for x in usage) or not response.request_id:
                raise AccountingError('missing or invalid provider usage')
            self.budget.settle(ident,price.cost(*usage,cached_inputs=response.cached_input_tokens),{'input_tokens':usage[0],'output_tokens':usage[1],'cached_input_tokens':response.cached_input_tokens,'request_id':response.request_id})
            if response.finish_reason != 'stop' and not (request.tools and response.finish_reason=='tool_calls'):
                raise AccountingError('provider did not finish normally; reported usage settled')
            if not isinstance(response.content,str) or len(response.content.encode())+len(json.dumps(response.tool_calls).encode())>100000 or response.output_tokens>request.max_output_tokens:
                raise AccountingError('provider output exceeded bounds')
            return response
        except BaseException as exc:
            self.budget.unresolved(ident, 'cancelled after submission' if isinstance(exc,asyncio.CancelledError) else type(exc).__name__)
            raise
