from dataclasses import asdict,replace
from decimal import Decimal,ROUND_FLOOR
import json
import math
from pathlib import Path
import statistics
import sqlite3
import asyncio

from .arms import ARMS,ExportArm
from .contracts import ArmResult,EvaluationInput
from .execution import execute_arm
from .score import score
from ..mission import load_mission
from ..evidence import EvidenceStore
from ..models.live import validate_live_config


def _recover_cost(destination,fallback_reservation=0):
    dbpath=Path(destination)/'run.db'
    if not dbpath.is_file():return {'settled_micro':0,'unresolved_micro':0,'model_calls':0}
    db=sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        row=db.execute('SELECT COALESCE(SUM(settled),0),COALESCE(SUM(CASE WHEN settled IS NULL THEN reserved ELSE 0 END),0),COUNT(*) FROM calls').fetchone()
        return dict(zip(('settled_micro','unresolved_micro','model_calls'),row))
    except sqlite3.Error:
        return {'settled_micro':0,'unresolved_micro':fallback_reservation,'model_calls':None}
    finally:db.close()


def _aggregate(results):
    grouped={}
    for result in results:
        if result['status']=='not_run':continue
        grouped.setdefault(result['arm'],[]).append(result)
    summaries={}
    for arm,rows in grouped.items():
        accuracy=[r['business_field_correctness'] for r in rows]
        latency=[r['latency_seconds'] for r in rows if isinstance(r.get('latency_seconds'),(int,float))]
        summaries[arm]={'runs':len(rows),'completed':sum(r['status']=='completed' for r in rows),'mean_business_field_correctness':statistics.mean(accuracy),
                        'accuracy_stdev':statistics.stdev(accuracy) if len(accuracy)>1 else None,'mean_latency_seconds':statistics.mean(latency) if latency else None,
                        'settled_micro':sum(r['settled_micro'] for r in rows) if all(type(r.get('settled_micro')) is int for r in rows) else None,
                        'unresolved_micro':sum(r['unresolved_micro'] for r in rows) if all(type(r.get('unresolved_micro')) is int for r in rows) else None}
    return summaries


def _markdown(report):
    lines=['# Architecture comparison report','',report['note'],'', '| Arm | Seed | Status | Fields correct | Cited-file coverage | Unsupported claims | Settled USD estimate | Unresolved USD | Calls | Latency s |', '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    def money(value):return f'{value/1e6:.6f}' if type(value) is int else 'unknown'
    for r in report['results']:
        if r['status']=='not_run':
            lines.append(f"| {r['arm']} | — | not_run | — | — | — | — | — | — | — |")
            continue
        claims=r.get('unsupported_claims')
        lines.append(f"| {r['arm']} | {r.get('metadata',{}).get('seed','—')} | {r['status']} | {r['business_field_correctness']:.2f} | {r['evidence_file_coverage']:.2f} | {len(claims) if isinstance(claims,list) else 'unmeasured'} | {money(r.get('settled_micro'))} | {money(r.get('unresolved_micro'))} | {r.get('model_calls','unknown')} | {r.get('latency_seconds','unknown')} |")
    lines.extend(['','Token-rated costs are not invoice reconciliation. DeepSeek uses the verified peak tariff as an upper estimate; off-peak invoices can be lower. Seeds control prompts/scheduling, not guaranteed provider RNG. Small or scripted runs establish no superiority.','', '## Enforcement differences',''])
    for r in report['results']:
        differences=r.get('metadata',{}).get('enforcement_differences',[])
        if differences:lines.append(f"- {r['arm']}: "+'; '.join(differences))
    return '\n'.join(lines)+'\n'


async def evaluate(config_path: Path,output: Path,*,budget_usd=None,models=None):
    config_path=Path(config_path).resolve()
    config=json.loads(config_path.read_text())
    def resolve(path):return (config_path.parent/path).resolve()
    mission=load_mission(resolve(config['mission']))
    gold=resolve(config['gold'])
    evidence=EvidenceStore(mission.manifest)
    if gold.is_relative_to(evidence.root) or any((evidence.root/ref).resolve()==gold or (evidence.root/ref).samefile(gold) for ref in evidence.files):
        raise ValueError('gold must be outside the evidence room')
    exports=config.get('exports',{})
    execute=config.get('execute',[])
    if not isinstance(execute,list) or len(execute)!=len(set(execute)) or set(exports)-set(ARMS) or set(execute)-set(ARMS) or set(exports)&set(execute):
        raise ValueError('unknown/duplicate/overlapping evaluation arms')
    seeds=config.get('seeds',[0])
    if not isinstance(seeds,list) or not seeds or any(type(s) is not int for s in seeds):
        raise ValueError('seeds must be nonempty integer list')
    if len(seeds)!=1 and exports:
        raise ValueError('one export is one recorded run, not repeated seed executions; evaluate each export separately')
    if execute:
        if type(budget_usd) not in (int,float) or not math.isfinite(budget_usd) or budget_usd<=0:
            raise ValueError('execution requires an explicit positive total spend cap')
        model_config=json.loads(resolve(config['models']).read_text())
        per_micro=int((Decimal(str(budget_usd))*1000000/len(execute)/len(seeds)).to_integral_value(rounding=ROUND_FLOOR))
        if per_micro<1:raise ValueError('total cap too small for the requested run count')
        per_budget=per_micro/1000000
        validate_live_config(model_config,per_budget)
        mission=replace(mission,limits=replace(mission.limits,budget_usd=per_budget))
    output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('fresh report output directory required')
    output.mkdir(parents=True,exist_ok=True)
    results=[];cancelled=False;committed_micro=0
    for run_index,seed in enumerate(seeds):
        inputs=EvaluationInput(mission.brief,mission.rubric,mission.manifest,asdict(mission.limits),seed)
        for name in ARMS:
            if name in execute:
                destination=output/f'{name}-run-{run_index}-seed-{seed}'
                try:
                    if committed_micro+per_micro>int(Decimal(str(budget_usd))*1000000):
                        result=ArmResult(name,'budget_exhausted','',{'settled_micro':0,'unresolved_micro':0,'model_calls':0},'offline_fake' if models is not None else 'live',{'seed':seed,'issues':['outer total cap cannot safely fund another matched run']})
                    else:
                        result=None
                    kwargs={'seed':seed,'models':models}
                    if name=='frozen_v1':kwargs['v1_root']=resolve(config.get('v1_root','../self_organizing_agents_v1.0'))
                    if result is None:result=await execute_arm(name,mission,model_config,per_budget,destination,**kwargs)
                except asyncio.CancelledError:
                    result=ArmResult(name,'cancelled','',_recover_cost(destination,per_micro),'offline_fake' if models is not None else 'live',{'seed':seed,'issues':['evaluation cancelled']})
                except Exception as exc:
                    result=ArmResult(name,'failed','',{'execution_errors':1,**_recover_cost(destination,per_micro)},'offline_fake' if models is not None else 'live',{'seed':seed,'issues':[type(exc).__name__+': '+str(exc)[:1000]]})
                committed_micro+=result.metrics.get('settled_micro',0)+result.metrics.get('unresolved_micro',0)
                result.metadata.update({'run_index':run_index,'matched_limits':asdict(mission.limits),'evidence_hashes':evidence.files})
            else:
                result=await ExportArm(name,resolve(exports[name]) if name in exports else None).run(inputs)
            if result.status=='not_run':
                results.append({'arm':name,'status':'not_run','reason':result.metadata['reason']})
            else:
                results.append(score(result,gold,mission.manifest))
            if result.status=='cancelled':cancelled=True;break
        if cancelled:break
    active_rows=[r for r in results if r['arm'] in execute]
    spent=sum(r.get('settled_micro',0) or 0 for r in active_rows)
    unresolved=sum(r.get('unresolved_micro',0) or 0 for r in active_rows)
    budget={'total_cap_usd':budget_usd if execute else None,'per_run_cap_usd':per_budget if execute else None,'settled_micro':spent,'unresolved_micro':unresolved,'status':'cancelled' if cancelled else 'finished'}
    report={'format_version':1,'results':results,'aggregate':_aggregate(results),'budget':budget,'note':'Executed architectures share evidence, rubric, configured model choices, per-run budget and deadline. Inspect enforcement differences. No superiority claim follows from a small sample.' if execute else 'Export scoring only. Missing arms are not simulated, repeats are not fabricated, and scripted results establish no live superiority.'}
    (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (output/'report.md').write_text(_markdown(report))
    return report
