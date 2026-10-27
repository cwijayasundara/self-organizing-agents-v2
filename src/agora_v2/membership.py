from dataclasses import asdict, dataclass
import json
import uuid

from .mission import Limits
from .profiles import Profile


@dataclass(frozen=True)
class HelperProposal:
    requester: str
    capability: str
    task_ids: tuple[str, ...]
    model_key: str
    budget_micro: int
    evidence: tuple[str, ...]
    reason: str


class Membership:
    def __init__(self, ledger, profiles: dict[str, Profile], limits: Limits, available=lambda: 0, slots_available=lambda: True):
        self.ledger = ledger
        self.profiles = profiles
        self.limits = limits
        self.available = available
        self.slots_available = slots_available

    def bootstrap(self, model_keys: list[str]):
        if len(model_keys) != self.limits.bootstrap_peers or any(k not in self.profiles for k in model_keys):
            raise ValueError('invalid bootstrap roster')
        if len({self.profiles[k].family for k in model_keys}) < 2:
            raise ValueError('two model families required')
        with self.ledger.transaction():
            if self.ledger.db.execute('SELECT 1 FROM peers').fetchone():
                raise ValueError('bootstrap already performed')
            for i, key in enumerate(model_keys, 1):
                p = self.profiles[key]
                self.ledger.db.execute("INSERT INTO peers VALUES(?,?,?,'ready',1,'general')", (f'p{i}', p.family, key))
                self.ledger.event(f'p{i}', 'peer_joined', {'family':p.family,'model_key':key,'bootstrap':True})

    def _validate(self, p: HelperProposal):
        l = self.ledger
        l.active_peer(p.requester)
        if l.closed:
            raise ValueError('admission closed')
        profile = self.profiles.get(p.model_key)
        if profile is None or p.capability not in profile.capabilities:
            raise ValueError('model/capability not allowed')
        if not p.task_ids or not p.evidence or not p.reason.strip():
            raise ValueError('helper needs tasks, evidence and reason')
        if type(p.budget_micro) is not int or p.budget_micro <= 0 or p.budget_micro > self.available():
            raise ValueError('helper budget unavailable')
        for ident in p.task_ids:
            if not l.db.execute("SELECT 1 FROM tasks WHERE id=? AND state!='approved'", (ident,)).fetchone():
                raise ValueError('helper task unavailable')
        for row in l.db.execute("SELECT proposal,state FROM helper_proposals WHERE state IN ('pending','admitted')"):
            other = json.loads(row['proposal'])
            if other['capability'] == p.capability and set(other['task_ids']) == set(p.task_ids):
                if row['state'] == 'pending':
                    raise ValueError('duplicate helper proposal')
                if l.db.execute("SELECT 1 FROM peers WHERE capability=? AND bootstrap=0 AND state NOT IN ('retired','failed')", (p.capability,)).fetchone():
                    raise ValueError('duplicate active helper')

    def propose(self, proposal: HelperProposal) -> str:
        with self.ledger.transaction():
            self._validate(proposal)
            ident = uuid.uuid4().hex
            self.ledger.db.execute('INSERT INTO helper_proposals(id,requester,proposal) VALUES(?,?,?)', (ident, proposal.requester, json.dumps(asdict(proposal))))
            self.ledger.event(proposal.requester, 'helper_proposed', {'proposal_id': ident, **asdict(proposal)})
            return ident

    def review(self, proposal_id: str, reviewer: str, approve: bool) -> str | None:
        l = self.ledger
        with l.transaction():
            l.active_peer(reviewer)
            row = l.db.execute('SELECT * FROM helper_proposals WHERE id=?', (proposal_id,)).fetchone()
            if row is None or row['state'] != 'pending' or reviewer == row['requester'] or type(approve) is not bool:
                raise ValueError('independent review required')
            p = HelperProposal(**json.loads(row['proposal']))
            ident = None
            if approve:
                # Temporarily exclude this proposal from duplicate validation in the same transaction.
                l.db.execute("UPDATE helper_proposals SET state='checking' WHERE id=?", (proposal_id,))
                self._validate(p)
                total = l.db.execute('SELECT COUNT(*) FROM peers').fetchone()[0]
                active = l.db.execute("SELECT COUNT(*) FROM peers WHERE state NOT IN ('retired','failed')").fetchone()[0]
                if total >= self.limits.total_identities:
                    raise ValueError('total identities exhausted')
                if active >= self.limits.active_contexts or not self.slots_available():
                    raise ValueError('no helper capacity')
                if len({r[0] for r in l.db.execute("SELECT family FROM peers WHERE state NOT IN ('retired','failed')")}) < 2:
                    raise ValueError('independent review family unavailable')
                ident = f'p{total+1}'
                profile = self.profiles[p.model_key]
                l.db.execute("INSERT INTO peers VALUES(?,?,?,'ready',0,?)", (ident, profile.family, p.model_key, p.capability))
                l.event(ident, 'peer_joined', {'family':profile.family,'model_key':p.model_key,'bootstrap':False,'reason':p.reason,'proposal_id':proposal_id,'budget_micro':p.budget_micro})
            l.db.execute('UPDATE helper_proposals SET state=?,reviewer=?,reason=? WHERE id=?', ('admitted' if approve else 'rejected', reviewer, 'useful' if approve else 'not useful', proposal_id))
            l.event(reviewer, 'helper_reviewed', {'proposal_id':proposal_id,'approved':approve,'peer_id':ident})
            return ident

    def retire(self, peer_id: str, reason: str):
        l = self.ledger
        with l.transaction():
            peer = l.active_peer(peer_id)
            if not reason.strip():
                raise ValueError('retirement needs a reason')
            held = l.db.execute('SELECT 1 FROM tasks WHERE holder=?', (peer_id,)).fetchone()
            if peer['bootstrap'] and held:
                raise ValueError('bootstrap peer holds work')
            remaining = l.db.execute("SELECT * FROM peers WHERE id!=? AND state NOT IN ('retired','failed','draining')", (peer_id,)).fetchall()
            if len(remaining) < 2 or len({r['family'] for r in remaining}) < 2:
                raise ValueError('retirement would strand independent reviews')
            for row in l.db.execute("SELECT id FROM tasks WHERE holder=?", (peer_id,)).fetchall():
                l.db.execute("UPDATE tasks SET state='open',holder=NULL,token=NULL,expires=NULL WHERE id=?", (row['id'],))
                l.event(peer_id,'claim_released',{'task_id':row['id'],'reason':'retirement'})
            l.db.execute("UPDATE peers SET state='retired' WHERE id=?", (peer_id,))
            l.event(peer_id, 'peer_retired', {'reason':reason})
