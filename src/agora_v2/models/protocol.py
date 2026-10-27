from dataclasses import dataclass
from typing import Protocol
from decimal import Decimal, ROUND_CEILING
from ..budget import AccountingError


@dataclass(frozen=True)
class ModelRequest:
    model_key: str
    prompt: str
    max_output_tokens: int = 1000
    messages: tuple[dict, ...] | None = None
    tools: tuple[dict, ...] | None = None


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int | None
    output_tokens: int | None
    request_id: str
    cached_input_tokens: int = 0
    finish_reason: str = "stop"
    tool_calls: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Price:
    input_micro_per_token: float
    output_micro_per_token: float
    cached_input_micro_per_token: float | None = None

    def cost(self, inputs: int, outputs: int, cached_inputs: int = 0) -> int:
        try:
            a,b=Decimal(str(self.input_micro_per_token)),Decimal(str(self.output_micro_per_token))
            if not a.is_finite() or not b.is_finite() or a<=0 or b<=0:
                raise ValueError()
            c = a if self.cached_input_micro_per_token is None else Decimal(str(self.cached_input_micro_per_token))
            if not c.is_finite() or c <= 0 or type(cached_inputs) is not int or not 0 <= cached_inputs <= inputs:
                raise ValueError()
            return int((a*(inputs-cached_inputs)+c*cached_inputs+b*outputs).to_integral_value(rounding=ROUND_CEILING))
        except (ValueError,ArithmeticError):
            raise AccountingError('unknown or invalid price')


class Model(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...
