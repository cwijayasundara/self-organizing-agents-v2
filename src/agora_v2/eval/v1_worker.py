"""External-process contract using frozen v1's public arun_swarm(models=...)."""
import asyncio
import contextlib
import io
import json
from pathlib import Path
import os
import sys
import threading

wire_in,wire_out=sys.stdin,sys.stdout
lock=threading.RLock()


def send(value):
    wire_out.write(json.dumps(value)+'\n');wire_out.flush()


def rpc(**fields):
    with lock:
        send({'op':'v1_call',**fields})
        line=wire_in.readline()
        if not line:raise RuntimeError('metered host bridge closed')
        result=json.loads(line)
        if 'error' in result:raise RuntimeError(result['error'])
        return result


class Sink(io.TextIOBase):
    def write(self,text):return len(text)


async def run(config):
    root=Path(config['v1_root'])
    sys.path.insert(0,str(root/'src'))
    from pydantic import Field
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage,convert_to_openai_messages
    from langchain_core.outputs import ChatGeneration,ChatResult
    from langchain_core.utils.function_calling import convert_to_openai_tool
    from agora.api import arun_swarm
    from agora.config import RosterConfig
    from agora.templates import load_template
    from agora.domain import build_domain

    class MeteredChat(BaseChatModel):
        model_key:str
        bound_tools:list[dict]=Field(default_factory=list)
        @property
        def _llm_type(self):return 'agora-v2-metered-proxy'
        def bind_tools(self,tools,**kwargs):
            return self.model_copy(update={'bound_tools':[convert_to_openai_tool(t) for t in tools]})
        def _generate(self,messages,stop=None,run_manager=None,**kwargs):
            wire=convert_to_openai_messages(messages)
            if wire and wire[0].get('role')=='system':wire[0]['content'] += '\nEvaluation repetition seed: '+str(config.get('seed',0))
            result=rpc(model_key=self.model_key,messages=wire,tools=self.bound_tools)
            calls=[]
            for call in result.get('tool_calls',[]):
                calls.append({'name':call['function']['name'],'args':json.loads(call['function']['arguments']),'id':call['id'],'type':'tool_call'})
            message=AIMessage(content=result['content'],tool_calls=calls,usage_metadata={'input_tokens':result['input_tokens'],'output_tokens':result['output_tokens'],'total_tokens':result['input_tokens']+result['output_tokens'],'input_token_details':{'cache_read':result.get('cached_input_tokens',0)}},response_metadata={'finish_reason':result['finish_reason']})
            return ChatResult(generations=[ChatGeneration(message=message)])
        async def _agenerate(self,messages,stop=None,run_manager=None,**kwargs):
            return await asyncio.to_thread(self._generate,messages,stop,run_manager,**kwargs)
        def get_num_tokens(self,text):return len(text.encode())+1024
        def get_num_tokens_from_messages(self,messages,tools=None):return len(json.dumps(convert_to_openai_messages(messages)).encode())+1024

    roster=RosterConfig.model_validate(config['roster'])
    models={key:MeteredChat(model_key=key) for key in roster.models}
    specs=load_template(root/'examples/evidence_review/template.yaml')
    validators,admission=build_domain('evidence_review',config['evidence_root'])
    send({'op':'v1_started','revision':config['revision'],'credential_env_present':any(k.endswith('_API_KEY') for k in os.environ),'peers':[{'id':p.id,'model':p.model,'family':roster.models[p.model].family} for p in roster.peers]})
    outcome=await arun_swarm(roster,specs,config['brief'],config['db_path'],models=models,validators=validators,admission=admission)
    try:
        artifact=outcome.ledger.artifacts.latest('synthesis')
        send({'op':'v1_result','native_status':outcome.result.status,'memo':artifact.content if artifact else '', 'native_spent_usd':outcome.result.spent_usd})
    finally:outcome.ledger.db.close()


try:
    config=json.loads(wire_in.readline())
    with contextlib.redirect_stdout(Sink()),contextlib.redirect_stderr(Sink()):
        asyncio.run(run(config))
except BaseException as exc:
    send({'op':'error','error':type(exc).__name__+': '+str(exc)[:500]})
    sys.exit(1)
