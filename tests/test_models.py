import asyncio
import pytest
from agora_v2.models import ModelRequest, ModelResponse, ScriptedModel, Gateway, Price
from agora_v2.budget import Budget, AccountingError
from agora_v2.slots import ExecutionSlots
from agora_v2.ledger import Ledger
from agora_v2.mission import Limits


async def test_gateway_settles_usage_and_rejects_missing_usage(tmp_path):
    with Ledger(tmp_path/'db') as l:
        b=Budget(l,Limits())
        g=Gateway({'fake':ScriptedModel([ModelResponse('ok',3,2,'id'),ModelResponse('bad',None,None,'id2')])},{'fake':Price(1,2)},b)
        slots=ExecutionSlots(5)
        async with slots.enter('peer','p') as ex:
            response=await g.call(ModelRequest('fake','hello',10),'exploration',ex)
            assert response.content=='ok'
            with pytest.raises(AccountingError):
                await g.call(ModelRequest('fake','hello',10),'review',ex)
        assert b.totals()['settled_micro']==7
        assert b.totals()['unresolved_micro']>0
        with pytest.raises(AccountingError):
            await g.call(ModelRequest('unknown','hi',10),'review',None)


async def test_submitted_cancel_keeps_liability(tmp_path):
    started=asyncio.Event()
    class Hanging:
        async def complete(self,request):
            started.set()
            await asyncio.Event().wait()
    with Ledger(tmp_path/'db') as l:
        b=Budget(l,Limits())
        g=Gateway({'fake':Hanging()},{'fake':Price(1,1)},b)
        slots=ExecutionSlots(1)
        async def work():
            async with slots.enter('peer','p') as ex:
                await g.call(ModelRequest('fake','hello',10),'review',ex)
        t=asyncio.create_task(work())
        await started.wait()
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
        assert b.totals()['unresolved_micro']>0
        assert slots.active==0
