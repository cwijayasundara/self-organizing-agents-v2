"""Frozen v1 runs externally; only provider injection uses the v2 host gateway."""
import asyncio
from contextlib import suppress
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import time
import uuid

from .contracts import ArmResult
from .execution import Session,_metrics
from .judge import judge_memo
from ..budget import BudgetExhausted
from ..business.evidence_review import validate_memo
from ..models import ModelRequest
from ..runtime import RunResult
from ..trace import export_run

V1_REVISION='b2bc646aa51b7444a22670283d462b59b7ddde22'


async def _revision(root):
    proc=await asyncio.create_subprocess_exec('git','-C',str(root),'rev-parse','HEAD',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
    raw,_=await proc.communicate()
    if proc.returncode!=0 or raw.decode().strip()!=V1_REVISION:raise ValueError('v1 source revision differs from frozen comparison revision')
    proc=await asyncio.create_subprocess_exec('git','-C',str(root),'diff','--quiet','HEAD','--',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    if proc.returncode!=0:raise ValueError('frozen v1 source has local tracked changes')


def materialize_evidence(evidence, destination):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=False)
    for item in evidence.metadata():
        path=destination/item.ref
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(evidence.read_all(item.ref,max_chars=1000000).encode('utf-8'))
        path.chmod(0o444)
    return destination


def _roster(session,config):
    first,second=config['bootstrap'][:2]
    models={}
    for key,spec in config['models'].items():
        models[key]={'provider':'openai','id':spec['id'],'family':spec['family'],'api':'chat','reasoning_effort':'none','price':{'in_per_m':spec['input_micro_per_token'],'cached_per_m':spec['cached_input_micro_per_token'],'out_per_m':spec['output_micro_per_token']}}
    return {'run_name':'frozen-v1-comparison','models':models,'peers':[{'id':f'P{i+1:02d}','model':key,'lens':lens} for i,(key,lens) in enumerate([(first,'quantities'),(second,'source credibility'),(first,'operations'),(second,'independent review')])],
            'budget':{'swarm_usd':session.mission.limits.budget_usd,'peer_usd':session.mission.limits.budget_usd,'wall_clock_s':max(1,int(session.mission.limits.wall_seconds)),'stagger_s':0,'idle_poll_s':.1,'stall_after_s':10,'stuck_turn_s':session.mission.limits.wall_seconds,'lease_s':120},'data_dir':str(session.native_evidence_root)}


async def run_frozen_v1(mission,config,budget_usd,output,v1_root,*,seed=0,models=None):
    root=Path(v1_root).resolve()
    python=root/'.venv/bin/python'
    if not python.is_file():raise ValueError('frozen v1 interpreter missing; provide its existing checkout without copying its environment')
    await _revision(root)
    session=Session(mission,config,budget_usd,output,seed,models,register_solver=False)
    session.actor='P01'
    session.native_evidence_root=materialize_evidence(session.evidence,session.output/'v1-evidence')
    session.model_config.update({'architecture':'frozen_v1','v1_revision':V1_REVISION})
    request={'v1_root':str(root),'revision':V1_REVISION,'seed':seed,'brief':mission.brief,'evidence_root':str(session.native_evidence_root),'db_path':str((session.output/'frozen-v1.sqlite').resolve()),'roster':_roster(session,config)}
    proc=None;status='failed';issues=[];decision={};start=time.monotonic()
    async def run():
        nonlocal proc,status,decision
        proc=await asyncio.create_subprocess_exec(str(python),'-B',str(Path(__file__).with_name('v1_worker.py').resolve()),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1','PYTHONUNBUFFERED':'1'},cwd=session.output,start_new_session=True,limit=1100000)
        proc.stdin.write((json.dumps(request)+'\n').encode());await proc.stdin.drain()
        total=0
        while True:
            line=await proc.stdout.readline();total+=len(line)
            if not line:raise RuntimeError('frozen v1 process exited without a result')
            if total>10000000:raise RuntimeError('v1 export protocol limit')
            message=json.loads(line)
            op=message.get('op')
            if op=='v1_started':
                if message['credential_env_present']:raise RuntimeError('credentials entered v1 child environment')
                for peer in message['peers']:session.ledger.register_peer(peer['id'],peer['family'],peer['model'])
                session.ledger.event('runtime','v1_started',message)
            elif op=='v1_call':
                if message['model_key'] not in config['models']:raise ValueError('v1 requested an ungranted model')
                messages=tuple(message['messages']);tools=tuple(message['tools'])
                wire=json.dumps({'messages':messages,'tools':tools},ensure_ascii=False)
                async with session.slots.enter('peer','v1-dispatch-'+uuid.uuid4().hex) as ex:
                    response=await session.gateway.call(ModelRequest(message['model_key'],wire,2000,messages,tools),'exploration',ex)
                proc.stdin.write((json.dumps(asdict(response))+'\n').encode());await proc.stdin.drain()
            elif op=='v1_result':
                if message['memo']:
                    session.publish(message['memo'])
                    errors=validate_memo(session.final_memo,session.evidence)
                    if not errors:
                        approved,decision=await judge_memo(session,session.final_memo)
                        status='completed' if approved and message['native_status']=='done' else 'insufficient_evidence'
                    else:issues.extend(errors);status='insufficient_evidence'
                else:status={'timed_out':'timed_out','stalled':'stalled','budget_exhausted':'budget_exhausted','cancelled':'cancelled'}.get(message['native_status'],'failed')
                session.ledger.event('runtime','v1_result',message)
                return
            elif op=='error':raise RuntimeError(message['error'])
            else:raise ValueError('unrecognized v1 export operation')
    try:
        async with asyncio.timeout(mission.limits.wall_seconds):await run()
    except BudgetExhausted as exc:status='budget_exhausted';issues.append(str(exc))
    except TimeoutError:status='timed_out'
    except asyncio.CancelledError:status='cancelled'
    except Exception as exc:issues.append(type(exc).__name__+': '+str(exc)[:1000])
    finally:
        if proc is not None and proc.returncode is None:
            with suppress(ProcessLookupError):os.killpg(proc.pid,signal.SIGTERM)
            try:await asyncio.wait_for(proc.wait(),2)
            except TimeoutError:
                with suppress(ProcessLookupError):os.killpg(proc.pid,signal.SIGKILL)
                await proc.wait()
        session.ledger.db.execute("UPDATE meta SET value='1' WHERE key='closed'")
        for row in session.ledger.db.execute('SELECT id FROM peers').fetchall():
            session.ledger.db.execute("UPDATE peers SET state='retired' WHERE id=?",(row['id'],))
            session.ledger.event(row['id'],'peer_retired',{'reason':'frozen v1 arm shutdown'})
        session.ledger.event('runtime','run_finished',{'status':status,'issues':issues,'cost':session.budget.totals()})
        latency=time.monotonic()-start
        export_run(session,RunResult(status,tuple(issues),latency))
        metrics=_metrics(session.ledger,session.budget,latency,decision)
        session.ledger.close()
    return ArmResult('frozen_v1',status,session.final_memo,metrics,session.mode,{'seed':seed,'issues':issues,'v1_revision':V1_REVISION,'model_revisions':config['models'],'enforcement_differences':['frozen v1 uses four fixed peers and its original task template','models injected through public arun_swarm(models=...); API dispatch serialized by bounded stdio bridge','v1 native episode scheduling/leases differ; host enforces global spend/call/time caps','v1 productive calls use exploration allowance; final independent judge uses protected allowance']})
