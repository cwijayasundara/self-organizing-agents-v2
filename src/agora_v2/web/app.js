'use strict';
let trace=null,cursor=0,timer=null,follow=true;
const $=id=>document.getElementById(id);
function node(tag,text,cls){const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;return el;}
function card(parent,title,details,cls){const el=node('div','',cls);el.append(node('strong',title));for(const detail of details)el.append(node('small',detail));parent.append(el);}
function reduce(events){
 const state={peers:{},tasks:{},leaves:{},reservations:{},settled:0,calls:0,scope:0,status:'running',memo_artifact_id:null};
 for(const e of events){const p=e.payload;switch(e.type){
 case 'peer_joined':state.peers[e.actor]={state:'ready',family:p.family,reason:p.reason||'Bootstrap generalist'};break;
 case 'peer_state':if(state.peers[e.actor])state.peers[e.actor].state=p.state;break;
 case 'peer_retired':if(state.peers[e.actor])Object.assign(state.peers[e.actor],{state:'retired',reason:p.reason});break;
 case 'task_proposed':state.tasks[p.task_id]={key:p.key,state:'open',final:p.spec.final};break;
 case 'task_claimed':if(state.tasks[p.task_id])Object.assign(state.tasks[p.task_id],{state:'claimed by '+e.actor});break;
 case 'claim_released':case 'claim_expired':if(state.tasks[p.task_id])state.tasks[p.task_id].state='open';break;
 case 'artifact_published':if(state.tasks[p.task_id]){state.tasks[p.task_id].state='awaiting independent review';if(state.tasks[p.task_id].final)state.memo_artifact_id=p.artifact_id;}break;
 case 'final_memo_published':state.memo_artifact_id=p.artifact_id;break;
 case 'artifact_reviewed':{const a=trace.artifacts.find(a=>a.id===p.artifact_id);if(a&&state.tasks[a.task])state.tasks[a.task].state=p.approved?'reviewed':'repair requested';break;}
 case 'scope_reviewed':if(p.approved){state.scope=p.scope_version;for(const t of Object.values(state.tasks))if(t.final)t.state='scope updated; final must be checked';}break;
 case 'semantic_call_started':state.leaves[p.identity]='analyzing supplied evidence';break;
 case 'semantic_call_finished':state.leaves[p.identity]='returned stored result';break;
 case 'call_reserved':state.reservations[p.call_id]=p.reserved_micro;state.calls++;break;
 case 'call_settled':state.settled+=p.settled_micro;delete state.reservations[p.call_id];break;
 case 'run_finished':state.status=p.status;break;
 }}return state;
}
function describe(e){const p=e.payload;const names={peer_joined:'Joined the ledger',helper_proposed:'Proposed temporary capacity',helper_reviewed:p.approved?'Helper admitted independently':'Helper declined',peer_retired:'Retired',finding_published:'Published evidence finding',scope_reviewed:p.approved?'Scope independently approved':'Scope needs revision',artifact_reviewed:p.approved?'Artifact independently reviewed':'Artifact needs repair'};return [names[e.type]||e.type.replaceAll('_',' '),p.reason||p.content||p.key||(p.approved===undefined?'':String(p.approved))].filter(Boolean).join(' · ');}
function render(){
 if(!trace)return;
 const visible=trace.events.slice(0,cursor),s=reduce(visible);
 $('mode').textContent=trace.mode==='scripted'?'SCRIPTED REPLAY · SYNTHETIC USAGE':trace.mode==='offline_fake'?'FAKE PROVIDERS · REAL RUNTIME':trace.mode.toUpperCase()+' · READ ONLY';
 $('cursor').max=trace.events.length;$('cursor').value=cursor;$('position').textContent=`${cursor} / ${trace.events.length} events`;
 $('metrics').replaceChildren();for(const [value,label] of [[s.status,'run status'],[Object.keys(s.peers).length,'peer identities'],[s.calls,'model calls'],[`$${(s.settled/1e6).toFixed(6)}`,'settled · '+(['scripted','offline_fake'].includes(trace.mode)?'synthetic':'usage estimate')]]){const el=node('div','','metric');el.append(node('strong',value),node('span',label));$('metrics').append(el);}
 $('peers').replaceChildren();for(const [id,p] of Object.entries(s.peers))card($('peers'),id,[p.family,p.state,p.reason],'peer '+p.state);
 $('tasks').replaceChildren();for(const t of Object.values(s.tasks))card($('tasks'),t.key,[t.state],'task');
 $('leaves').replaceChildren();for(const [id,status] of Object.entries(s.leaves))card($('leaves'),id.split(':').slice(0,2).join(' · '),[status,'No task claims or voting authority'],'leaf');if(!Object.keys(s.leaves).length)$('leaves').append(node('p','No semantic calls in the displayed events.','muted'));
 $('events').replaceChildren();for(const e of visible.slice(-70).reverse()){const li=node('li',describe(e));li.append(node('small',`#${e.seq} · ${e.actor}`));$('events').append(li);}
 $('memo').textContent=(trace.artifacts.find(a=>a.id===s.memo_artifact_id)||{}).content||'';$('memo-note').textContent=`Scope v${s.scope} · Unresolved reservations: $${(Object.values(s.reservations).reduce((a,b)=>a+b,0)/1e6).toFixed(6)}`;
}
$('cursor').oninput=()=>{follow=false;cursor=Number($('cursor').value);render();};
$('start').onclick=()=>{follow=false;cursor=0;render();};$('end').onclick=()=>{follow=true;cursor=trace.events.length;render();};
$('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;$('play').textContent='Play events';return;}follow=false;if(cursor>=trace.events.length)cursor=0;$('play').textContent='Pause';timer=setInterval(()=>{cursor=Math.min(cursor+1,trace.events.length);render();if(cursor===trace.events.length){clearInterval(timer);timer=null;$('play').textContent='Play events';}},220);};
async function refresh(){try{const response=await fetch('/api/snapshot');if(!response.ok)throw Error('Run unavailable');trace=await response.json();if(follow)cursor=trace.events.length;render();}catch(e){$('mode').textContent=e.message;}}
refresh();setInterval(refresh,2000);
if(typeof module!=='undefined')module.exports={reduce};
