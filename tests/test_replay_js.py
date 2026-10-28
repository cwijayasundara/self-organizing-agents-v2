import json
from pathlib import Path
import shutil
import subprocess
import pytest


def browser_state(events, artifacts=()):
    app=Path(__file__).resolve().parents[1]/'src/agora_v2/web/app.js'
    script=r'''
const vm=require('node:vm'),fs=require('node:fs');
const context={module:{exports:{}},document:{getElementById:()=>({})},setInterval:()=>0,fetch:()=>new Promise(()=>{})};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
const input=JSON.parse(fs.readFileSync(0,'utf8'));
console.log(JSON.stringify(context.module.exports.reduce(input.events,{artifacts:input.artifacts})));
'''
    result=subprocess.run(['node','-e',script,str(app)],input=json.dumps({'events':events,'artifacts':artifacts}),check=True,capture_output=True,text=True)
    return json.loads(result.stdout)


def event(seq, actor, kind, **payload):
    return {'seq':seq,'actor':actor,'type':kind,'payload':payload}


@pytest.mark.skipif(shutil.which('node') is None,reason='Node required')
def test_board_exposes_full_findings_and_only_published_artifacts_at_cursor():
    events=[event(1,'p1','peer_joined',family='glm',model_key='glm',bootstrap=True),
            event(2,'p1','finding_published',content='<img src=x onerror=alert(1)> Finding',evidence=['cost_model.csv']),
            event(3,'system','task_proposed',task_id='cost',key='Costs',spec={'final':False}),
            event(4,'p1','artifact_published',task_id='cost',artifact_id='a',version=1)]
    artifacts=[{'id':'a','task':'cost','author':'p1','content':'Full cost calculation','evidence':'["cost_model.csv"]','version':1}]
    before=browser_state(events[:3],artifacts)
    assert [m['content'] for m in before['board'] if m['category']=='finding']==['<img src=x onerror=alert(1)> Finding']
    assert not before['artifacts']
    after=browser_state(events,artifacts)
    assert after['board'][-1]['content']=='Full cost calculation'
    assert after['board'][-1]['evidence']==['cost_model.csv']


@pytest.mark.skipif(shutil.which('node') is None,reason='Node required')
def test_review_targets_exact_visible_artifact_and_task_owner_releases_after_publish():
    events=[event(1,'p1','peer_joined',family='glm',bootstrap=True),
            event(2,'p2','peer_joined',family='deepseek',bootstrap=True),
            event(3,'system','task_proposed',task_id='final',key='Memo',spec={'final':True}),
            event(4,'p1','task_claimed',task_id='final'),
            event(5,'p1','artifact_published',task_id='final',artifact_id='old',version=1),
            event(6,'p2','artifact_reviewed',artifact_id='old',approved=True,reason='Checked the evidence'),
            event(7,'p1','artifact_published',task_id='final',artifact_id='new',version=2)]
    artifacts=[{'id':'old','task':'final','author':'p1','content':'First memo','version':1},
               {'id':'new','task':'final','author':'p1','content':'Second memo','version':2}]
    claimed=browser_state(events[:4],artifacts)
    assert claimed['tasks']['final']['holder']=='p1'
    reviewed=browser_state(events[:6],artifacts)
    assert reviewed['tasks']['final']['state']=='done' and reviewed['tasks']['final']['holder'] is None
    assert reviewed['board'][-1]['content']=='Checked the evidence'
    assert reviewed['memo_artifact_id']=='old'
    revised=browser_state(events,artifacts)
    assert revised['tasks']['final']['state']=='review' and revised['memo_artifact_id']=='new'


@pytest.mark.skipif(shutil.which('node') is None,reason='Node required')
def test_helpers_and_call_costs_follow_event_history_without_future_state():
    events=[event(1,'p1','peer_joined',family='glm',model_key='glm',bootstrap=True),
            event(2,'p1','call_reserved',call_id='call',reserved_micro=100,purpose='exploration'),
            event(3,'gateway','call_settled',call_id='call',settled_micro=40,usage={'input_tokens':10,'output_tokens':5}),
            event(4,'p1','helper_proposed',proposal_id='h',reason='Reconcile costs',capability='arithmetic',task_ids=['cost'],model_key='deepseek',budget_micro=100000),
            event(5,'p4','peer_joined',family='deepseek',model_key='deepseek',bootstrap=False,proposal_id='h',reason='Reconcile costs'),
            event(6,'p2','helper_reviewed',proposal_id='h',approved=True,peer_id='p4'),
            event(7,'p4','peer_retired',reason='Review complete')]
    before=browser_state(events[:4])
    assert list(before['peers'])==['p1']
    assert before['peers']['p1']['settled']==40 and before['peers']['p1']['calls']==1
    assert before['reservations']=={} and before['settled']==40
    assert before['board'][-1]['content']=='Reconcile costs'
    assert before['board'][-1]['task_ids']==['cost']
    assert before['board'][-1]['requested_model']=='deepseek'
    assert before['board'][-1]['requested_budget_micro']==100000
    after=browser_state(events)
    assert after['peers']['p4']['bootstrap'] is False
    assert after['peers']['p4']['state']=='retired'
    assert after['board'][-1]['content']=='Review complete'


@pytest.mark.skipif(shutil.which('node') is None,reason='Node required')
def test_scope_amendments_remain_unresolved_until_independent_acceptance():
    events=[event(1,'p1','scope_proposed',proposal_id='initial',required=[],base_version=0),
            event(2,'p2','scope_reviewed',proposal_id='initial',approved=True,scope_version=1,reason='Accepted'),
            event(3,'p1','scope_proposed',proposal_id='amendment',required=['cost'],base_version=1),
            event(4,'p2','scope_reviewed',proposal_id='amendment',approved=False,scope_version=1,reason='Revise'),
            event(5,'p1','scope_proposed',proposal_id='replacement',required=['cost'],base_version=1),
            event(6,'p2','scope_reviewed',proposal_id='replacement',approved=True,scope_version=2,reason='Accepted')]
    pending=browser_state(events[:3])
    assert pending['scopes']['amendment']['state']=='pending'
    rejected=browser_state(events[:4])
    assert rejected['scopes']['amendment']['state']=='rejected'
    accepted=browser_state(events)
    assert accepted['scope']==2
    assert accepted['scopes']['amendment']['state']=='superseded'
    assert accepted['scopes']['replacement']['state']=='accepted'


@pytest.mark.skipif(shutil.which('node') is None,reason='Node required for browser reducer regression')
def test_replay_cursor_uses_artifact_version_published_at_that_event():
    app=Path(__file__).resolve().parents[1]/'src/agora_v2/web/app.js'
    script=r'''
const vm=require('node:vm'),fs=require('node:fs');
const context={module:{exports:{}},document:{getElementById:()=>({})},setInterval:()=>0,fetch:()=>new Promise(()=>{})};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
const events=[{actor:'system',type:'task_proposed',payload:{task_id:'final',key:'memo',spec:{final:true}}},{actor:'p1',type:'artifact_published',payload:{task_id:'final',artifact_id:'old'}},{actor:'p1',type:'artifact_published',payload:{task_id:'final',artifact_id:'new'}}];
console.log(JSON.stringify(context.module.exports.reduce(events.slice(0,2))));
'''
    result=subprocess.run(['node','-e',script,str(app)],check=True,capture_output=True,text=True)
    assert json.loads(result.stdout).get('memo_artifact_id')=='old'
