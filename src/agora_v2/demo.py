"""Explicit scripted replay using real ledger transitions and synthetic models."""
from collections import deque
from importlib.resources import files
import json
from pathlib import Path

from .actions import ActionDispatcher
from .budget import Budget
from .context import ContextStore
from .evidence import EvidenceStore
from .ledger import Ledger,TaskSpec
from .membership import Membership
from .mission import load_mission
from .models import Gateway,ModelResponse,Price,ScriptedModel
from .profiles import Profile
from .runtime import Runtime
from .slots import ExecutionSlots


def fixture_path():
    packaged=Path(str(files('agora_v2').joinpath('data/evidence_review')))
    return packaged if packaged.exists() else Path(__file__).resolve().parents[2]/'examples/evidence_review'


class ReplayModel:
    def __init__(self, steps):
        self.steps=deque(steps)

    async def complete(self, request):
        payload=json.loads(request.prompt)
        snapshot=payload['snapshot']
        step=self.steps.popleft()
        if step['peer']!=snapshot['identity']:
            raise ValueError('script schedule/model mismatch')
        def resolve(value):
            if isinstance(value,list):
                return [resolve(v) for v in value]
            if isinstance(value,dict):
                return {k:resolve(v) for k,v in value.items()}
            if not isinstance(value,str) or not value.startswith('$'):
                return value
            kind,_,key=value[1:].partition(':')
            if kind=='task':
                return next(t['id'] for t in snapshot['tasks'] if t['key']==key)
            if kind=='artifact':
                task=resolve('$task:'+key)
                return next(a['id'] for a in reversed(snapshot['artifacts']) if a['task']==task)
            if kind=='scope':
                return snapshot['scopes'][-1]['id']
            if kind=='helper':
                return snapshot['helper_proposals'][-1]['id']
            raise ValueError('unknown replay reference')
        text=json.dumps(resolve(step['action']))
        return ModelResponse(text,max(1,len(request.prompt)//4),max(1,len(text)//4),'scripted-request')


def build_runtime(output: Path):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    if (output/'run.db').exists():
        raise ValueError('run output already exists; choose a new directory')
    fixture=fixture_path()
    mission=load_mission(fixture/'mission.json')
    steps=json.loads((fixture/'replay.json').read_text())
    ledger=Ledger(output/'run.db')
    budget=Budget(ledger,mission.limits)
    slots=ExecutionSlots(mission.limits.active_contexts)
    profiles={'one':Profile('one','scripted-family-one',('general','arithmetic')),'two':Profile('two','scripted-family-two',('general','arithmetic'))}
    membership=Membership(ledger,profiles,mission.limits,budget.available,lambda:slots.active<mission.limits.active_contexts)
    membership.bootstrap(['one','two','one'])
    ledger.propose_task(TaskSpec('final','Produce the business memo',{'type':'string'},(),mission.rubric,final=True))
    model=ReplayModel(steps)
    checker=ScriptedModel([ModelResponse(json.dumps({'covered':[True]*len(mission.rubric),'unsupported_claims':[],'issues':[]}),100,20,'scripted-check')])
    gateway=Gateway({'one':model,'two':model,'checker':checker},{k:Price(.001,.001) for k in ('one','two','checker')},budget)
    context=ContextStore(output/'context')
    dispatcher=ActionDispatcher(ledger,membership,EvidenceStore(mission.manifest),context)
    return Runtime(mission,ledger,membership,gateway,budget,slots,dispatcher,output,'scripted',[s['peer'] for s in steps])


async def replay(output: Path):
    runtime=build_runtime(output)
    try:
        return await runtime.run(runtime.mission)
    finally:
        runtime.ledger.close()
