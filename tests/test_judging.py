import json
import pytest
from agora_v2.eval.judge import parse_judgment


def test_claim_judge_rejects_truthy_nonbooleans_and_reports_unsupported_claims():
    approved,data=parse_judgment(json.dumps({'covered':[True]*5,'unsupported_claims':['Unsupported productivity gain'],'issues':[]}),5)
    assert not approved and data['unsupported_claims']==['Unsupported productivity gain']
    approved,data=parse_judgment(json.dumps({'covered':[1]*5,'unsupported_claims':[],'issues':[]}),5)
    assert not approved and data['unsupported_claims'] is None


async def test_judge_does_not_silently_drop_evidence_after_first_preview(tmp_path):
    import hashlib
    from types import SimpleNamespace
    from agora_v2.evidence import EvidenceStore
    from agora_v2.ledger import Ledger
    from agora_v2.mission import Limits,Mission
    from agora_v2.models import Gateway,ModelResponse,Price
    from agora_v2.budget import Budget
    from agora_v2.slots import ExecutionSlots
    from agora_v2.eval.judge import judge_memo
    root=tmp_path/'data';root.mkdir()
    raw=('x'*10001+' TAILFACT').encode();(root/'long.txt').write_bytes(raw)
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'root':'data','files':{'long.txt':hashlib.sha256(raw).hexdigest()}}))
    class Checker:
        async def complete(self,request):
            assert 'TAILFACT' in request.prompt
            return ModelResponse('{"covered":[true],"unsupported_claims":[],"issues":[]}',100,10,'check')
    with Ledger(tmp_path/'db') as ledger:
        gateway=Gateway({'checker':Checker()},{'checker':Price(.01,.01)},Budget(ledger,Limits()))
        session=SimpleNamespace(mission=Mission('brief',('all evidence',),manifest),evidence=EvidenceStore(manifest),gateway=gateway,slots=ExecutionSlots(1),ledger=ledger)
        approved,_=await judge_memo(session,'memo')
        assert approved
