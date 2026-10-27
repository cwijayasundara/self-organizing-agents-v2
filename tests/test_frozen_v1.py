from dataclasses import replace
from pathlib import Path
import json
import pytest
from agora_v2.eval.frozen_v1 import run_frozen_v1
from agora_v2.models import ModelResponse
from agora_v2.mission import load_mission

ROOT=Path(__file__).resolve().parents[1]
V1=ROOT.parent/'self_organizing_agents_v1.0'
pytestmark=[pytest.mark.v1,pytest.mark.skipif(not (V1/'.venv/bin/python').exists(),reason='frozen v1 checkout/interpreter required')]


async def test_frozen_v1_uses_public_model_injection_and_shared_call_limit(tmp_path,monkeypatch):
    monkeypatch.setenv('GLM_API_KEY','must-not-reach-v1-child')
    mission=load_mission(ROOT/'examples/evidence_review/mission.json')
    mission=replace(mission,limits=replace(mission.limits,wall_seconds=15,model_calls=2))
    config=json.loads((ROOT/'examples/models.example.json').read_text())
    class Fake:
        async def complete(self,request):
            assert request.messages and request.tools
            return ModelResponse('Waiting for independent evidence.',10,10,'fake-v1')
    result=await run_frozen_v1(mission,config,1,tmp_path/'run',V1,models={k:Fake() for k in config['models']})
    assert result.metrics['model_calls']==2
    assert result.status=='budget_exhausted'
    trace=json.loads((tmp_path/'run/trace.json').read_text())
    ready=next(e['payload'] for e in trace['events'] if e['type']=='v1_started')
    assert ready['credential_env_present'] is False
    assert ready['revision']=='b2bc646aa51b7444a22670283d462b59b7ddde22'
