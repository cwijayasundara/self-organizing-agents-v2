import json
from pathlib import Path
import pytest
from agora_v2.smoke import run_smoke
from agora_v2.models import ModelResponse

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.sandbox
async def test_smoke_requires_real_author_subcall_and_preserves_usage(tmp_path):
    class Fake:
        async def complete(self,request):
            if request.messages:
                text="```repl\npart=context['evidence']['cost_model.csv'][:50]\nresult=llm_query(part,model='leaf')\nanswer['content']='verified '+result\nanswer['ready']=True\n```"
            else:text='OK'
            return ModelResponse(text,20,50,'fake-smoke')
    config=json.loads((ROOT/'examples/models.example.json').read_text())
    report=await run_smoke(config,.1,tmp_path/'smoke',models={k:Fake() for k in config['models']})
    assert report['status']=='completed'
    assert report['mode']=='offline_fake'
    assert report['cost']['calls']==5
    assert report['semantic_calls']==1
    assert report['cost']['unresolved_micro']==0
    assert (tmp_path/'smoke/smoke.json').exists()
