import pytest
from agora_v2.models.live import validate_live_config


def valid_config():
    return {'models':{'glm':{'provider':'glm','id':'glm-5.3-flash','family':'glm','key_env':'GLM_API_KEY','input_micro_per_token':.15,'cached_input_micro_per_token':.03,'output_micro_per_token':.5},'deepseek':{'provider':'deepseek','id':'deepseek-flash','family':'deepseek','key_env':'DEEPSEEK_API_KEY','input_micro_per_token':.3,'cached_input_micro_per_token':.006,'output_micro_per_token':1.2}},'bootstrap':['glm','deepseek','glm'],'checker':'deepseek'}


def test_live_requires_explicit_positive_cap_and_two_real_families():
    config=valid_config()
    for cap in [None,0,-1,float('nan')]:
        with pytest.raises(ValueError,match='cap'):
            validate_live_config(config,cap)
    with pytest.raises(ValueError,match='families'):
        validate_live_config(config|{'bootstrap':['glm']*3},1)
    assert validate_live_config(config,1)['checker']=='deepseek'


def test_unknown_prices_and_adapter_gate_cannot_be_overridden_by_config():
    config=valid_config()
    del config['models']['glm']['input_micro_per_token']
    with pytest.raises(ValueError,match='price'):
        validate_live_config(config,1)
    with pytest.raises(ValueError,match='unknown live configuration'):
        validate_live_config(valid_config()|{'author_adapter_verified':True},1)
