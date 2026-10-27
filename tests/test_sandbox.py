import asyncio
import json
from pathlib import Path
import pytest
from agora_v2.context.docker import DockerExecutor
from agora_v2.context import ContextStore
from agora_v2.slots import ExecutionSlots
from agora_v2.ledger import Ledger
from agora_v2.budget import Budget
from agora_v2.mission import Limits
from agora_v2.models import Gateway,ScriptedModel,ModelResponse,Price

pytestmark=pytest.mark.sandbox


async def test_real_container_runs_semantic_bridge_and_isolates_host(tmp_path,monkeypatch):
    monkeypatch.setenv("AGORA_TEST_SECRET","must-not-cross-container-boundary")
    store=ContextStore(tmp_path/'context')
    h=store.put('cost\n36\n45\n22\n312\n52\n40',('cost_model.csv',))
    l=Ledger(tmp_path/'db')
    budget=Budget(l,Limits())
    slots=ExecutionSlots(1)
    gateway=Gateway({'fake':ScriptedModel([ModelResponse('507 thousand EUR',4,4,'fake')])},{'fake':Price(.01,.01)},budget)
    executor=DockerExecutor(store,gateway,slots)
    code=f'''import os,socket
assert not os.path.exists('/Users')
assert not os.path.exists('/eval/gold')
assert 'AGORA_TEST_SECRET' not in os.environ
assert 'OPENAI_API_KEY' not in os.environ
assert 'ANTHROPIC_API_KEY' not in os.environ
try:
    socket.create_connection(('1.1.1.1',53),timeout=.2)
    raise AssertionError('unrestricted network')
except OSError: pass
try:
    open('/write','w')
    raise AssertionError('root writable')
except OSError: pass
value=read_context({h!r})
total=sum(int(x) for x in value.splitlines()[1:])
assert total==507
result=semantic_call('fake',[{h!r}],'Check the total',100)
RESULT=store_value(str(total)+' '+result['preview']['text'],[{h!r}])
'''
    async with slots.enter('peer','p') as ex:
        result=await executor.execute(code,[h],ex)
    assert '507 507 thousand EUR' in result['preview']['text']
    assert result['preview']['evidence']==('cost_model.csv',)
    assert slots.peak==1 and budget.totals()['calls']==1
    await executor.close()
    assert not executor.containers
    l.close()


async def test_runaway_timeout_and_output_limit_cleanup(tmp_path):
    store=ContextStore(tmp_path/'context')
    executor=DockerExecutor(store,None,ExecutionSlots(1),timeout_seconds=2)
    slots=executor.slots
    async with slots.enter('peer','p') as ex:
        with pytest.raises((TimeoutError,RuntimeError)):
            await executor.execute('while True: pass',[],ex)
        with pytest.raises(RuntimeError):
            await executor.execute("print('x'*200000)",[],ex)
    await executor.close()
    assert not executor.containers


async def test_cancel_during_semantic_call_removes_real_container(tmp_path):
    started=asyncio.Event()
    class Hanging:
        async def complete(self,request):
            started.set()
            await asyncio.Event().wait()
    store=ContextStore(tmp_path/'context')
    h=store.put('evidence',('README.md',))
    l=Ledger(tmp_path/'db')
    budget=Budget(l,Limits())
    slots=ExecutionSlots(1)
    gateway=Gateway({'fake':Hanging()},{'fake':Price(.01,.01)},budget)
    executor=DockerExecutor(store,gateway,slots)
    async def work():
        async with slots.enter('peer','p') as ex:
            return await executor.execute(f"semantic_call('fake',[{h!r}],'check',100)",[h],ex)
    task=asyncio.create_task(work())
    await asyncio.wait_for(started.wait(),10)
    names=list(executor.containers)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task,10)
    assert not executor.containers and slots.active==0
    assert budget.totals()['unresolved_micro']>0
    for name in names:
        proc=await asyncio.create_subprocess_exec('docker','inspect',name,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        assert proc.returncode!=0
    await executor.close()
    l.close()
