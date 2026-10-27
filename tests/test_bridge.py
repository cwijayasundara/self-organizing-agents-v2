import pytest
from agora_v2.context.bridge import SemanticBridge
from agora_v2.context import ContextStore
from agora_v2.ledger import Ledger
from agora_v2.budget import Budget
from agora_v2.mission import Limits
from agora_v2.models import Gateway,ScriptedModel,ModelResponse,Price
from agora_v2.slots import ExecutionSlots


async def test_bridge_limits_handles_depth_and_preserves_evidence(tmp_path):
    store=ContextStore(tmp_path/'context')
    h=store.put('evidence',('README.md',))
    l=Ledger(tmp_path/'db')
    budget=Budget(l,Limits())
    slots=ExecutionSlots(1)
    g=Gateway({'fake':ScriptedModel([ModelResponse('analysis',2,2,'id')])},{'fake':Price(.01,.01)},budget)
    bridge=SemanticBridge(store,g,slots,[h])
    async with slots.enter('peer','p') as ex:
        result=await bridge.dispatch({'op':'semantic_call','model_key':'fake','handles':[h],'instruction':'check','max_output_tokens':100},ex)
        assert result['preview']['text']=='analysis'
        assert result['preview']['evidence']==('README.md',)
        with pytest.raises(ValueError):
            await bridge.dispatch({'op':'read_context','handle':'../gold'},ex)
        with pytest.raises(ValueError):
            await bridge.dispatch({'op':'claim','task_id':'anything'},ex)
    assert slots.peak==1 and slots.active==0
    assert budget.totals()['calls']==1
    l.close()
