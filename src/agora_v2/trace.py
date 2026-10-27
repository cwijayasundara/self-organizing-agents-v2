from dataclasses import asdict
import json
from pathlib import Path


def snapshot(ledger):
    return {name:[dict(r) for r in ledger.db.execute(f'SELECT * FROM {name}')] for name in ('peers','tasks','artifacts','scopes','helper_proposals','calls')}


def export_run(runtime, result):
    data=snapshot(runtime.ledger)
    final=runtime.ledger.db.execute('SELECT a.content FROM artifacts a JOIN tasks t ON t.id=a.task WHERE t.final=1 ORDER BY a.version DESC LIMIT 1').fetchone()
    data.update({'format_version':1,'mode':runtime.mode,'status':result.status,'issues':result.issues,'events':runtime.ledger.events(),
                 'cost':runtime.budget.totals(),'pricing':'synthetic' if runtime.mode=='scripted' else 'configured provider prices',
                 'limits':asdict(runtime.mission.limits),'brief':runtime.mission.brief,'rubric':runtime.mission.rubric,
                 'evidence_hashes':runtime.evidence.files,'scope_version':runtime.ledger.scope_version,'context_objects':len(runtime.context.records),
                 'final_memo':final[0] if final else '', 'latency_seconds':result.latency_seconds})
    path=runtime.output/'trace.json'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)
    return path


def peer_snapshot(ledger):
    """Artifact bodies stay external; peers receive IDs and bounded previews."""
    data=snapshot(ledger)
    for artifact in data['artifacts']:
        body=artifact['content']
        artifact['content']=body[:1000]
        artifact['content_truncated']=len(body)>1000
    return data
