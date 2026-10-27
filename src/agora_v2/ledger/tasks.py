from dataclasses import asdict, dataclass
import json
import math
import unicodedata
import uuid


@dataclass(frozen=True)
class TaskSpec:
    deliverable_key: str
    objective: str
    output_schema: dict
    evidence_requirements: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    final: bool = False


@dataclass(frozen=True)
class Task:
    id: str
    key: str


@dataclass(frozen=True)
class Claim:
    task_id: str
    peer_id: str
    token: str
    expires_at: float


@dataclass(frozen=True)
class ClaimResult:
    ok: bool
    claim: Claim | None = None
    reason: str = ''
    holder: str | None = None
    expires_at: float | None = None


class Tasks:
    def propose_task(self, spec: TaskSpec) -> Task:
        key = ' '.join(unicodedata.normalize('NFKC', spec.deliverable_key).casefold().split())
        if not key or not spec.objective or not spec.acceptance_criteria or not isinstance(spec.output_schema, dict):
            raise ValueError('incomplete task specification')
        with self.transaction():
            if self.closed:
                raise ValueError('admission closed')
            row = self.db.execute('SELECT id,key FROM tasks WHERE key=?', (key,)).fetchone()
            if row:
                return Task(row['id'], row['key'])
            for dep in spec.dependencies:
                if not self.db.execute('SELECT 1 FROM tasks WHERE id=?', (dep,)).fetchone():
                    raise ValueError('missing dependency')
            if spec.final and self.db.execute('SELECT 1 FROM tasks WHERE final=1').fetchone():
                raise ValueError('only one final deliverable')
            ident = uuid.uuid4().hex
            self.db.execute('INSERT INTO tasks(id,key,spec,final) VALUES(?,?,?,?)', (ident, key, json.dumps(asdict(spec)), spec.final))
            self.db.executemany('INSERT INTO dependencies VALUES(?,?)', [(ident, d) for d in spec.dependencies])
            self.event('system', 'task_proposed', {'task_id': ident, 'key': key, 'spec': asdict(spec)})
            return Task(ident, key)

    def claim(self, task_id: str, peer_id: str, lease_seconds: float = 30) -> ClaimResult:
        if not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise ValueError('invalid lease')
        with self.transaction():
            self.active_peer(peer_id)
            if self.closed:
                return ClaimResult(False, reason='claims closed')
            row = self.db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:
                raise ValueError('unknown task')
            if row['state'] in ('published', 'approved', 'failed'):
                return ClaimResult(False, reason='task already published')
            if row['holder'] and row['expires'] > self.clock():
                return ClaimResult(False, reason='contended', holder=row['holder'], expires_at=row['expires'])
            if row['final'] and (self.scope_version == 0 or self.unresolved_scope()):
                return ClaimResult(False, reason='scope requires independent approval')
            blocked = self.db.execute("SELECT 1 FROM dependencies d JOIN tasks t ON t.id=d.dependency WHERE d.task=? AND t.state!='approved'", (task_id,)).fetchone()
            if blocked:
                return ClaimResult(False, reason='dependencies not reviewed')
            claim = Claim(task_id, peer_id, uuid.uuid4().hex, self.clock() + lease_seconds)
            self.db.execute("UPDATE tasks SET state='claimed',holder=?,token=?,expires=? WHERE id=?", (peer_id, claim.token, claim.expires_at, task_id))
            self.event(peer_id, 'task_claimed', asdict(claim))
            return ClaimResult(True, claim)

    def check_claim(self, claim: Claim):
        row = self.db.execute('SELECT * FROM tasks WHERE id=?', (claim.task_id,)).fetchone()
        if row is None or row['holder'] != claim.peer_id or row['token'] != claim.token or row['expires'] <= self.clock():
            raise ValueError('stale lease')
        self.active_peer(claim.peer_id)
        return row

    def release(self, claim: Claim):
        with self.transaction():
            self.check_claim(claim)
            self.db.execute("UPDATE tasks SET state='open',holder=NULL,token=NULL,expires=NULL WHERE id=?", (claim.task_id,))
            self.event(claim.peer_id, 'claim_released', {'task_id': claim.task_id})

    def expire_claims(self, now: float) -> int:
        with self.transaction():
            rows = self.db.execute('SELECT id,holder FROM tasks WHERE holder IS NOT NULL AND expires<=?', (now,)).fetchall()
            for row in rows:
                self.db.execute("UPDATE tasks SET state='open',holder=NULL,token=NULL,expires=NULL WHERE id=?", (row['id'],))
                self.event(row['holder'], 'claim_expired', {'task_id': row['id']})
            return len(rows)
