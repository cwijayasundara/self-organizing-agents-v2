import asyncio
import json
from pathlib import Path
import pytest
from agora_v2.context.author import AuthorRLMExecutor
from agora_v2.context import ContextStore
from agora_v2.models import Gateway, ModelResponse, ScriptedModel, Price
from agora_v2.slots import ExecutionSlots
from agora_v2.budget import Budget, AccountingError
from agora_v2.mission import Limits
from agora_v2.ledger import Ledger

pytestmark=pytest.mark.sandbox


def components(tmp_path,models,limits=Limits()):
    l=Ledger(tmp_path/'db')
    store=ContextStore(tmp_path/'context')
    h=store.put('Amounts: 36,45,22,312,52,40',('cost_model.csv',))
    budget=Budget(l,limits)
    slots=ExecutionSlots(1)
    gateway=Gateway(models,{k:Price(.01,.01) for k in models},budget)
    return l,store,h,budget,slots,AuthorRLMExecutor(store,gateway,slots)


async def test_authors_engine_external_context_leaf_accounting_and_isolation(tmp_path):
    code="""```repl
import os
assert 'DEEPSEEK_API_KEY' not in os.environ
assert not os.path.exists('/eval/gold')
text = context['evidence']['cost_model.csv']
assert text == 'Amounts: 36,45,22,312,52,40'
result = llm_query('Check 36+45+22+312+52+40',model='leaf')
answer['content'] = '507 '+result
answer['ready'] = True
```"""
    class Root:
        async def complete(self,request):
            assert 'Amounts: 36,45,22,312,52,40' not in request.prompt
            return ModelResponse(code,30,90,'root-id')
    l,store,h,budget,slots,executor=components(tmp_path,{'root':Root(),'leaf':ScriptedModel([ModelResponse('checked',5,5,'leaf-id')])})
    async with slots.enter('peer','p') as ex:
        result=await executor.reason('root','Compute costs using evidence variables',[h],ex,leaf_model='leaf')
    assert store.get(result['handle'])==('507 checked',('cost_model.csv',))
    assert budget.totals()['calls']==2 and budget.totals()['settled_micro']>0
    assert slots.peak==1 and slots.active==0
    assert not executor.containers
    l.close()


async def test_author_batch_calls_share_gateway_and_missing_usage_is_not_zero(tmp_path):
    code="""```repl
parts=llm_query_batched(['a','b'],model='leaf')
answer['content']=';'.join(parts)
answer['ready']=True
```"""
    l,store,h,budget,slots,executor=components(tmp_path,{'root':ScriptedModel([ModelResponse(code,10,50,'root')]),'leaf':ScriptedModel([ModelResponse('A',2,2,'a'),ModelResponse('B',3,3,'b')])})
    async with slots.enter('peer','p') as ex:
        result=await executor.reason('root','Partition',[h],ex,leaf_model='leaf')
    assert store.get(result['handle'])[0]=='A;B'
    assert budget.totals()['calls']==3 and slots.peak==1
    l.close()


async def test_author_active_cancel_preserves_liability_and_removes_container(tmp_path):
    started=asyncio.Event()
    class Hanging:
        async def complete(self,request):
            started.set()
            await asyncio.Event().wait()
    l,store,h,budget,slots,executor=components(tmp_path,{'root':Hanging()})
    async def work():
        async with slots.enter('peer','p') as ex:
            await executor.reason('root','Analyze',[h],ex)
    task=asyncio.create_task(work())
    await asyncio.wait_for(started.wait(),20)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task,10)
    assert budget.totals()['unresolved_micro']>0
    assert slots.active==0 and not executor.containers
    l.close()


async def test_author_missing_usage_and_call_cap_stop_before_an_unmetered_leaf(tmp_path):
    from agora_v2.budget import BudgetExhausted
    code="```repl\nanswer['content']=llm_query('check',model='leaf')\nanswer['ready']=True\n```"
    l,store,h,budget,slots,executor=components(tmp_path,{'root':ScriptedModel([ModelResponse(code,10,30,'root')]),'leaf':ScriptedModel([ModelResponse('unused',2,2,'leaf')])},Limits(model_calls=1))
    async with slots.enter('peer','p') as ex:
        with pytest.raises(BudgetExhausted):
            await executor.reason('root','analyze',[h],ex,leaf_model='leaf')
    assert budget.totals()['calls']==1 and not executor.containers
    l.close()
    other=tmp_path/'missing';other.mkdir()
    l,store,h,budget,slots,executor=components(other,{'root':ScriptedModel([ModelResponse('unknown',None,None,'id')])})
    async with slots.enter('peer','p') as ex:
        with pytest.raises(AccountingError):
            await executor.reason('root','analyze',[h],ex)
    assert budget.totals()['unresolved_micro']>0 and not executor.containers
    l.close()


async def test_named_root_alias_in_leaf_query_is_still_a_metered_leaf(tmp_path):
    code="```repl\nanswer['content']=llm_query('check',model='root')\nanswer['ready']=True\n```"
    l,store,h,budget,slots,executor=components(tmp_path,{'root':ScriptedModel([ModelResponse(code,10,30,'root')]),'leaf':ScriptedModel([ModelResponse('checked',2,2,'leaf')])})
    async with slots.enter('peer','p') as ex:
        result=await executor.reason('root','analyze',[h],ex,leaf_model='leaf')
    assert store.get(result['handle'])[0]=='checked'
    assert len([e for e in l.events() if e['type']=='semantic_call_started'])==1
    l.close()
