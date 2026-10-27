import asyncio
from dataclasses import replace
from pathlib import Path
import pytest
from agora_v2.runtime import Runtime
from agora_v2.demo import build_runtime
from agora_v2.mission import load_mission,Limits
from agora_v2.models import ModelResponse

FIXTURE=Path(__file__).resolve().parents[1]/'examples/evidence_review'


@pytest.mark.parametrize('status',['cancelled','stalled','insufficient_evidence','failed','timed_out','budget_exhausted'])
async def test_terminal_paths_preserve_trace_and_release_resources(tmp_path,status):
    runtime=build_runtime(tmp_path/'run')
    if status=='cancelled':
        runtime.cancel()
    elif status=='timed_out':
        runtime.mission=replace(runtime.mission,limits=Limits(wall_seconds=.000001))
    elif status=='budget_exhausted':
        runtime.budget.cap=1
    elif status=='stalled':
        runtime.schedule=[]
    elif status=='insufficient_evidence':
        runtime.evidence.files['missing.txt']='bad'
    else:
        runtime.gateway.models['one']=object()
    result=await runtime.run(runtime.mission)
    assert result.status==status
    assert runtime.slots.active==0
    assert not runtime.ledger.db.execute('SELECT 1 FROM tasks WHERE holder IS NOT NULL').fetchone()
    assert (tmp_path/'run'/'trace.json').exists()
    runtime.ledger.close()


async def test_waiting_peers_stall_without_burning_all_calls(tmp_path):
    from agora_v2.models import ScriptedModel
    runtime=build_runtime(tmp_path/'run')
    runtime.schedule=None
    wait=ModelResponse('{"type":"wait"}',10,10,'wait')
    runtime.gateway.models['one']=ScriptedModel([wait]*40)
    runtime.gateway.models['two']=ScriptedModel([wait]*40)
    result=await runtime.run(runtime.mission)
    assert result.status=='stalled'
    assert runtime.budget.totals()['calls']<=6
    runtime.ledger.close()


async def test_active_cancel_preserves_submitted_liability_and_trace(tmp_path):
    runtime=build_runtime(tmp_path/'run')
    started=asyncio.Event()
    class Hanging:
        async def complete(self,request):
            started.set()
            await asyncio.Event().wait()
    runtime.gateway.models['one']=Hanging()
    work=asyncio.create_task(runtime.run(runtime.mission))
    await asyncio.wait_for(started.wait(),2)
    runtime.cancel()
    result=await asyncio.wait_for(work,2)
    assert result.status=='cancelled'
    assert runtime.slots.active==0
    assert runtime.budget.totals()['unresolved_micro']>0
    assert (tmp_path/'run/trace.json').exists()
    runtime.ledger.close()


@pytest.mark.parametrize('repairs,expected',[(0,'stalled'),(3,'failed')])
async def test_failed_holder_releases_work_without_resetting_task_repairs(tmp_path,repairs,expected):
    from agora_v2.ledger import TaskSpec
    from agora_v2.models import ScriptedModel
    runtime=build_runtime(tmp_path/'run')
    task=runtime.ledger.propose_task(TaskSpec('recovery','analyze',{},(),('checked',)))
    p=runtime.ledger.propose_scope('p2',[task.id],0)
    runtime.ledger.review_scope(p,'p3',True,'required')
    runtime.ledger.claim(task.id,'p1',480)
    runtime.ledger.db.execute("UPDATE tasks SET repairs=? WHERE id=?",(repairs,task.id))
    runtime.ledger.db.execute("UPDATE peers SET state='failed' WHERE id='p1'")
    runtime.schedule=['p2']
    runtime.gateway.models['two']=ScriptedModel([ModelResponse('{"type":"wait"}',10,10,'wait')])
    result=await runtime.run(runtime.mission)
    assert result.status==expected
    assert any(e['type']=='claim_released' and e['payload'].get('reason')=='peer failure' for e in runtime.ledger.events())
    if repairs:
        row=runtime.ledger.db.execute('SELECT state,repairs FROM tasks WHERE id=?',(task.id,)).fetchone()
        assert row['state']=='failed' and row['repairs']==3
    runtime.ledger.close()
