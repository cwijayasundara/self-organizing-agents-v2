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
