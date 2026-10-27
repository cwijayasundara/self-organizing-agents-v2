import asyncio
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
        # Byte count plus adapter envelope allowance conservatively bounds tokens.
        reserved=price.cost(len(request.prompt.encode())+1024,request.max_output_tokens)
        ident=self.budget.reserve(getattr(execution,"billing_identity",execution.identity),purpose,reserved)
        self.budget.submitted(ident)
        try:
            response=await self.models[request.model_key].complete(request)
            usage=(response.input_tokens,response.output_tokens)
            if any(type(x) is not int or x<0 for x in usage) or not response.request_id:
                raise AccountingError('missing or invalid provider usage')
            self.budget.settle(ident,price.cost(*usage),{'input_tokens':usage[0],'output_tokens':usage[1],'request_id':response.request_id})
            if not isinstance(response.content,str) or len(response.content.encode())>100000 or response.output_tokens>request.max_output_tokens:
                raise AccountingError('provider output exceeded bounds')
            return response
        except BaseException as exc:
            self.budget.unresolved(ident, 'cancelled after submission' if isinstance(exc,asyncio.CancelledError) else type(exc).__name__)
            raise
