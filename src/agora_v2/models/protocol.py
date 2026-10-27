from dataclasses import dataclass
from typing import Protocol
from decimal import Decimal, ROUND_CEILING
from ..budget import AccountingError


@dataclass(frozen=True)
class ModelRequest:
    model_key: str
    prompt: str
    max_output_tokens: int = 1000


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int | None
    output_tokens: int | None
    request_id: str


@dataclass(frozen=True)
class Price:
    input_micro_per_token: float
    output_micro_per_token: float

    def cost(self, inputs: int, outputs: int) -> int:
        try:
            a,b=Decimal(str(self.input_micro_per_token)),Decimal(str(self.output_micro_per_token))
            if not a.is_finite() or not b.is_finite() or a<=0 or b<=0:
                raise ValueError()
            return int((a*inputs+b*outputs).to_integral_value(rounding=ROUND_CEILING))
        except (ValueError,ArithmeticError):
            raise AccountingError('unknown or invalid price')


class Model(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...
