import json
from pathlib import Path
from .contracts import ArmResult

ARMS=('frozen_v1','plain_single','external_context','dynamic_swarm','single_root_rlm')


class ExportArm:
    """Reads an existing export; never invokes or modifies v1."""
    def __init__(self,name: str,path: Path | None):
        self.name,self.path=name,path

    async def run(self, inputs):
        if self.path is None:
            return ArmResult(self.name,'not_run','',{},'unavailable',{'reason':'No export or execution requested for this arm'})
        data=json.loads(self.path.read_text())
        if data.get('format_version')!=1:
            raise ValueError('arm export requires format_version=1')
        cost=data.get('cost',{})
        metrics={'settled_micro':cost.get('settled_micro'),'unresolved_micro':cost.get('unresolved_micro'),
                 'model_calls':cost.get('calls'),'latency_seconds':data.get('latency_seconds'),
                 'peers':len(data['peers']) if isinstance(data.get('peers'),list) else None,
                 'membership_changes':sum(e['type'] in ('peer_joined','peer_retired') for e in data.get('events',[])),
                 'execution_errors':sum(e['type'] in ('action_rejected','execution_error') for e in data.get('events',[]))}
        differences=[]
        if data.get('brief')!=inputs.brief: differences.append('original brief differs or is missing')
        if data.get('rubric')!=list(inputs.rubric): differences.append('rubric differs or is missing')
        if data.get('limits')!=inputs.limits: differences.append('limits differ or are missing')
        from ..evidence import EvidenceStore
        if data.get('evidence_hashes')!=EvidenceStore(inputs.manifest).files: differences.append('evidence hashes differ or are missing')
        differences.extend(data.get('enforcement_differences',[]))
        return ArmResult(self.name,data.get('status','unknown'),data.get('final_memo',''),metrics,data.get('mode','imported'),
                         {'enforcement_differences':differences,'seed':inputs.seed,'source_export':str(self.path),
                          'model_revisions':data.get('model_revisions'),'live_comparable':False})
