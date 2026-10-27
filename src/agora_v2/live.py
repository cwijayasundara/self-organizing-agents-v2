"""Construction and lifecycle of non-scripted provider-backed runs."""
from dataclasses import asdict, replace
from pathlib import Path
import json

from .actions import ActionDispatcher
from .budget import Budget
from .context import ContextStore
from .context.author import AuthorRLMExecutor, AUTHOR_IMAGE, verify_author_image
from .evidence import EvidenceStore
from .ledger import Ledger, TaskSpec
from .membership import Membership
from .models import Gateway
from .models.live import LiveModel, model_price, validate_live_config, PRICE_VERIFIED_DATE
from .profiles import Profile
from .runtime import Runtime
from .slots import ExecutionSlots


def evidence_handles(evidence, context):
    handles=[]
    for metadata in evidence.metadata():
        chunks=[]
        for start in range(0, metadata.size+1, evidence.MAX_READ):
            chunk=evidence.read(metadata.ref,start,evidence.MAX_READ)
            chunks.append(chunk)
            if len(chunk)<evidence.MAX_READ:break
        handles.append(context.put(''.join(chunks),(metadata.ref,)))
    return handles


async def build_live_runtime(mission, config, budget_usd, output, *, models=None, image_verifier=verify_author_image):
    validate_live_config(config,budget_usd)
    verified=await image_verifier(AUTHOR_IMAGE)
    output=Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('run output must be a fresh empty directory')
    # Fail before creating a run if a required credential is missing.
    provider_models=models if models is not None else {key:LiveModel(spec) for key,spec in config['models'].items()}
    if set(provider_models)!=set(config['models']):
        raise ValueError('model implementations must match the configured allowlist')
    output.mkdir(parents=True,exist_ok=True)
    mission=replace(mission,limits=replace(mission.limits,budget_usd=budget_usd))
    evidence=EvidenceStore(mission.manifest)
    ledger=Ledger(output/'run.db')
    budget=Budget(ledger,mission.limits)
    slots=ExecutionSlots(mission.limits.active_contexts)
    profiles={key:Profile(key,spec['family'],('general','arithmetic','source_credibility','operations','evidence_partition')) for key,spec in config['models'].items()}
    membership=Membership(ledger,profiles,mission.limits,budget.available,lambda:slots.active<mission.limits.active_contexts)
    membership.bootstrap(config['bootstrap'])
    ledger.propose_task(TaskSpec('final','Deliver the memo required by the immutable original brief',{'type':'string'},(),mission.rubric,final=True))
    prices={key:model_price(spec) for key,spec in config['models'].items()}
    routed=dict(provider_models)
    checker=config.get('checker',config['bootstrap'][1])
    routed['checker']=provider_models[checker]
    prices['checker']=prices[checker]
    gateway=Gateway(routed,prices,budget)
    context=ContextStore(output/'context')
    executor=AuthorRLMExecutor(context,gateway,slots,timeout_seconds=min(120,mission.limits.wall_seconds))
    executor.evidence_handles=evidence_handles(evidence,context)
    executor.leaf_model=config.get('leaf',checker)
    dispatcher=ActionDispatcher(ledger,membership,evidence,context,executor,lease_seconds=mission.limits.wall_seconds)
    runtime=Runtime(mission,ledger,membership,gateway,budget,slots,dispatcher,output,'offline_fake' if models is not None else 'live',reasoner=executor)
    runtime.model_config={'models':config['models'],'bootstrap':config['bootstrap'],'checker':checker,'leaf':executor.leaf_model,'price_verified_date':PRICE_VERIFIED_DATE,'author_image':verified,'lease_seconds':mission.limits.wall_seconds,'cost_basis':'reported token usage with configured tariffs; DeepSeek peak upper tariff (invoice may be lower)'}
    (output/'configuration.json').write_text(json.dumps(runtime.model_config,indent=2)+'\n')
    ledger.event('runtime','run_started',{'mode':runtime.mode,'limits':asdict(mission.limits),'configuration':runtime.model_config})
    return runtime


async def run_live(mission,config,budget_usd,output,*,on_started=None):
    runtime=await build_live_runtime(mission,config,budget_usd,output)
    try:
        if on_started is not None:on_started(runtime)
        return await runtime.run(runtime.mission)
    finally:
        await runtime.dispatcher.executor.close()
        runtime.ledger.close()
