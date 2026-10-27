from pathlib import Path
import pytest
from agora_v2.models.live import validate_live_config,LiveUnavailable


def test_live_requires_explicit_positive_cap_and_two_families():
    config={'models':{'one':{'family':'a','input_micro_per_token':1,'output_micro_per_token':1},'two':{'family':'b','input_micro_per_token':1,'output_micro_per_token':1}},'bootstrap':['one','two','one']}
    for cap in [None,0,-1,float('nan')]:
        with pytest.raises(ValueError,match='cap'):
            validate_live_config(config,cap)
    with pytest.raises(ValueError,match='families'):
        validate_live_config(config|{'bootstrap':['one','one','one']},1)
    with pytest.raises(LiveUnavailable,match='author-package'):
        validate_live_config(config,1)


def test_unknown_prices_and_adapter_gate_cannot_be_overridden_by_config():
    config={'models':{'one':{'family':'a'},'two':{'family':'b'}},'bootstrap':['one','two','one'],'author_adapter_verified':True}
    with pytest.raises(ValueError,match='price'):
        validate_live_config(config,1)
