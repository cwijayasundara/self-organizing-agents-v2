from dataclasses import asdict
import json
from .ledger import TaskSpec, Claim
from .membership import HelperProposal


# A strict action vocabulary prevents model text from generating permissions.
FIELDS={
    'wait':set(), 'propose_task':{'key','objective','schema','evidence','criteria','dependencies'},
    'claim':{'task_id'}, 'publish':{'task_id','content','evidence','handle'},
    'review_artifact':{'artifact_id','approve','reason'}, 'propose_scope':{'required_task_ids','base_version'},
    'review_scope':{'proposal_id','approve','reason'}, 'propose_helper':{'capability','task_ids','model_key','budget_micro','evidence','reason'},
    'review_helper':{'proposal_id','approve'}, 'retire':{'reason'}, 'finding':{'content','evidence'},
    'read_evidence':{'ref','start','length'}, 'preview':{'handle','max_chars'}, 'slice':{'handle','start','length'},
    'execute':{'code','handles'}, 'read_artifact':{'artifact_id'},
}


class ActionDispatcher:
    def __init__(self, ledger, membership, evidence, context, executor=None):
        self.ledger,self.membership,self.evidence,self.context,self.executor=ledger,membership,evidence,context,executor

    def references(self, refs):
        if not isinstance(refs,(list,tuple)) or not all(isinstance(x,str) for x in refs):
            raise ValueError('invalid evidence list')
        for ref in refs:
            self.evidence.read(ref,0,0)
        return list(refs)

    async def apply(self, actor: str, action: dict, execution):
        l=self.ledger
        l.active_peer(actor)
        if not isinstance(action,dict) or action.get('type') not in FIELDS or set(action)-{'type'}-FIELDS[action['type']]:
            raise ValueError('unknown action or fields')
        kind=action['type']
        a={k:v for k,v in action.items() if k!='type'}
        if kind=='wait':
            return {'waiting':True}
        if kind=='propose_task':
            refs=self.references(a.get('evidence',[]))
            return asdict(l.propose_task(TaskSpec(a['key'],a['objective'],a['schema'],tuple(refs),tuple(a['criteria']),tuple(a.get('dependencies',[])))))
        if kind=='claim':
            return asdict(l.claim(a['task_id'],actor,30))
        if kind=='publish':
            row=l.db.execute('SELECT * FROM tasks WHERE id=?',(a['task_id'],)).fetchone()
            if row is None or row['holder']!=actor:
                raise ValueError('actor does not hold task')
            content=a.get('content')
            evidence=a.get('evidence',[])
            if 'handle' in a:
                content,stored_refs=self.context.get(a['handle'])
                evidence=list(set(evidence)|set(stored_refs))
            refs=self.references(evidence)
            result=l.publish(Claim(row['id'],actor,row['token'],row['expires']),content,refs)
            return {'id':result.id,'task_id':result.task_id,'author':result.author,'version':result.version,'content_preview':result.content[:1000],'content_truncated':len(result.content)>1000}
        if kind=='read_artifact':
            row=l.db.execute('SELECT content,evidence FROM artifacts WHERE id=?',(a['artifact_id'],)).fetchone()
            if row is None:
                raise ValueError('unknown artifact')
            h=self.context.put(row['content'],tuple(json.loads(row['evidence'])))
            return {'handle':h,'preview':asdict(self.context.preview(h,1000))}
        if kind=='review_artifact':
            l.review_artifact(a['artifact_id'],actor,a['approve'],a['reason'])
            return {'reviewed':a['artifact_id']}
        if kind=='propose_scope':
            return {'proposal_id':l.propose_scope(actor,a['required_task_ids'],a['base_version'])}
        if kind=='review_scope':
            return {'scope_version':l.review_scope(a['proposal_id'],actor,a['approve'],a['reason'])}
        if kind=='propose_helper':
            self.references(a['evidence'])
            return {'proposal_id':self.membership.propose(HelperProposal(actor,**a))}
        if kind=='review_helper':
            return {'peer_id':self.membership.review(a['proposal_id'],actor,a['approve'])}
        if kind=='retire':
            self.membership.retire(actor,a['reason'])
            return {'retired':True}
        if kind=='finding':
            refs=self.references(a['evidence'])
            if not isinstance(a['content'],str) or not 0<len(a['content'])<=10000:
                raise ValueError('invalid finding')
            with l.transaction():
                l.event(actor,'finding_published',{'content':a['content'],'evidence':refs})
            return {'published':True}
        if kind=='read_evidence':
            ref=a['ref']
            handle=self.context.put(self.evidence.read(ref,a.get('start',0),a.get('length',10000)),(ref,))
            return {'handle':handle,'preview':asdict(self.context.preview(handle,1000))}
        if kind=='preview':
            return asdict(self.context.preview(a['handle'],a.get('max_chars',1000)))
        if kind=='slice':
            return {'handle':self.context.slice(a['handle'],a['start'],a['length'])}
        if kind=='execute':
            if self.executor is None:
                raise ValueError('isolated context executor unavailable')
            return await self.executor.execute(a['code'],a['handles'],execution)
        raise ValueError('unsupported action')
