"""Explicitly capped provider-usage and authors' semantic-subcall verification."""
from dataclasses import replace
import asyncio
import json
from pathlib import Path
import time

from .context.author import AuthorRLMExecutor,verify_author_image
from .demo import fixture_path
from .eval.execution import Session
from .mission import load_mission
from .models import ModelRequest
from .runtime import RunResult
from .trace import export_run


async def run_smoke(config,budget_usd,output,*,models=None):
    await verify_author_image()
    mission=load_mission(fixture_path()/'mission.json')
    mission=replace(mission,limits=replace(mission.limits,model_calls=8,wall_seconds=240))
    session=Session(mission,config,budget_usd,output,0,models)
    session.model_config['architecture']='provider-smoke'
    executor=AuthorRLMExecutor(session.context,session.gateway,session.slots)
    start=time.monotonic();status='failed';issues=[]
    try:
        async with asyncio.timeout(mission.limits.wall_seconds):
            for key in config['models']:
                async with session.slots.enter('peer','smoke-'+key) as ex:
                    await session.gateway.call(ModelRequest(key,'Respond with exactly OK. This verifies reported API usage only.',512),'exploration',ex)
            h=session.context.put(session.evidence.read('cost_model.csv'),('cost_model.csv',))
            async with session.slots.enter('peer','smoke-root') as ex:
                result=await executor.reason(session.solver,'Infrastructure smoke: read a short slice of cost_model.csv from context evidence. Invoke llm_query once on that slice using model="leaf". Then set answer content to a short confirmation. Do not skip the semantic call.',[h],ex,leaf_model=session.leaf,max_output_tokens=1500)
            calls=sum(e['type']=='semantic_call_started' for e in session.ledger.events())
            if calls<1:raise RuntimeError('provider response did not exercise the required programmatic semantic subcall')
            session.final_memo=session.context.get(result['handle'])[0]
            status='completed'
    except asyncio.CancelledError:
        status='cancelled'
    except Exception as exc:
        issues.append(type(exc).__name__+': '+str(exc)[:1000])
    finally:
        try:await executor.close()
        except Exception as exc:status='failed';issues.append('executor cleanup failed: '+str(exc)[:500])
        session.ledger.db.execute("UPDATE meta SET value='1' WHERE key='closed'")
        session.ledger.db.execute("UPDATE peers SET state='retired'")
        session.ledger.event('runtime','run_finished',{'status':status,'issues':issues,'cost':session.budget.totals()})
        export_run(session,RunResult(status,tuple(issues),time.monotonic()-start))
        report={'status':status,'mode':session.mode,'issues':issues,'cost':session.budget.totals(),'semantic_calls':sum(e['type']=='semantic_call_started' for e in session.ledger.events()),'cost_basis':session.model_config['cost_basis']}
        (Path(output)/'smoke.json').write_text(json.dumps(report,indent=2)+'\n')
        session.ledger.close()
    return report
