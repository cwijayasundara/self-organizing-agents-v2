"""Live preflight. No provider dispatch until upstream controls are verified."""
import math
from .protocol import Price
from ..budget import AccountingError


class LiveUnavailable(RuntimeError):
    pass


def validate_live_config(config: dict, budget_usd: float | None):
    if type(budget_usd) not in (int,float) or not math.isfinite(budget_usd) or budget_usd<=0:
        raise ValueError('live mode requires an explicit positive spend cap')
    models=config.get('models',{})
    bootstrap=config.get('bootstrap',[])
    if len(bootstrap)!=3 or any(k not in models for k in bootstrap):
        raise ValueError('three allowlisted bootstrap models required')
    if len({models[k].get('family') for k in bootstrap})<2:
        raise ValueError('bootstrap must span two model families')
    for key in set(bootstrap):
        try:
            Price(models[key]['input_micro_per_token'],models[key]['output_micro_per_token']).cost(1,1)
        except (KeyError,TypeError,AccountingError):
            raise ValueError(f'known price required for {key}')
    # A user config cannot declare unverified integration controls proven.
    raise LiveUnavailable('Live author-package adapter is unverified; see docs/rlm-adapter-assessment.md. No provider request was submitted.')
