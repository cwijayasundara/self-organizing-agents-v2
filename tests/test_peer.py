import json
from pathlib import Path
import pytest
from agora_v2.actions import ActionDispatcher
from agora_v2.peer import Peer
from agora_v2.context import ContextStore
from agora_v2.ledger import Ledger
from agora_v2.membership import Membership
from agora_v2.profiles import Profile
from agora_v2.mission import load_mission
from agora_v2.evidence import EvidenceStore
from agora_v2.budget import Budget
from agora_v2.slots import ExecutionSlots
from agora_v2.models import Gateway,ScriptedModel,ModelResponse,Price

FIXTURE=Path(__file__).resolve().parents[1]/'examples/evidence_review'


def components(tmp_path,responses):
    mission=load_mission(FIXTURE/'mission.json')
    l=Ledger(tmp_path/'db')
    budget=Budget(l,mission.limits)
    profiles={'one':Profile('one','one',('general','arithmetic')),'two':Profile('two','two',('general','arithmetic'))}
    members=Membership(l,profiles,mission.limits,budget.available)
    members.bootstrap(['one','two','one'])
    gateway=Gateway({'one':ScriptedModel(responses)},{'one':Price(.01,.01)},budget)
    dispatcher=ActionDispatcher(l,members,EvidenceStore(mission.manifest),ContextStore(tmp_path/'context'))
    return l,dispatcher,Peer('p1','one',mission,gateway,dispatcher),ExecutionSlots(5)


def response(action):
    return ModelResponse(json.dumps(action),10,10,'fake-request')


async def test_peer_validates_authority_and_fences_invalid_output(tmp_path):
    l,d,peer,slots=components(tmp_path,[response({'type':'propose_task','peer_id':'p2'}),ModelResponse('not-json',10,10,'fake2'),response({'type':'wait'})])
    for _ in range(3):
        async with slots.enter('peer','p1') as ex:
            await peer.step({},ex)
    assert not l.db.execute('SELECT 1 FROM tasks').fetchone()
    assert len([e for e in l.events() if e['type']=='action_rejected'])==2
    assert l.db.execute("SELECT state FROM peers WHERE id='p1'").fetchone()[0]=='waiting'
    l.close()


async def test_evidence_loaded_into_external_handle_and_published(tmp_path):
    l,d,peer,slots=components(tmp_path,[response({'type':'read_evidence','ref':'README.md','start':0,'length':100})])
    async with slots.enter('peer','p1') as ex:
        result=await peer.step({},ex)
    assert result['preview']['evidence']==('README.md',)
    assert 'handle' in result
    assert len(result['preview']['text'])==100
    with pytest.raises(ValueError):
        await d.apply('p1',{'type':'read_evidence','ref':'../gold.json'},None)
    l.close()


async def test_repair_limit_fails_peer_instead_of_looping_forever(tmp_path):
    l,d,peer,slots=components(tmp_path,[ModelResponse('bad',10,10,'id')]*3)
    for _ in range(3):
        async with slots.enter('peer','p1') as ex:
            await peer.step({},ex)
    assert l.db.execute("SELECT state FROM peers WHERE id='p1'").fetchone()[0]=='failed'
    l.close()


async def test_review_dispatch_uses_protected_allowance(tmp_path):
    from agora_v2.ledger import TaskSpec
    l,d,peer,slots=components(tmp_path,[])
    task=l.propose_task(TaskSpec('cost','compute',{},(),('checked',)))
    artifact=l.publish(l.claim(task.id,'p2',30).claim,'checked',[])
    peer.gateway.models['one']=ScriptedModel([response({'type':'review_artifact','artifact_id':artifact.id,'approve':True,'reason':'verified'})])
    b=peer.gateway.budget
    ident=b.reserve('p2','exploration',800000)
    b.settle(ident,800000,{})
    from agora_v2.trace import snapshot
    async with slots.enter('peer','p1') as ex:
        await peer.step(snapshot(l),ex)
    assert l.db.execute('SELECT approved FROM artifacts WHERE id=?',(artifact.id,)).fetchone()[0]==1
    assert l.db.execute('SELECT purpose FROM calls ORDER BY rowid DESC LIMIT 1').fetchone()[0]=='review'
    l.close()
