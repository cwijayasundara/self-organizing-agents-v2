from dataclasses import dataclass
import json
import uuid


@dataclass(frozen=True)
class CompletionSnapshot:
    scope_version: int
    artifact_ids: tuple[str, ...]


class Scope:
    def propose_scope(self, author: str, required_task_ids: list[str], base_version: int) -> str:
        with self.transaction():
            self.active_peer(author)
            if self.closed or base_version != self.scope_version:
                raise ValueError('closed or stale scope')
            required = set(required_task_ids)
            final = self.db.execute('SELECT id FROM tasks WHERE final=1').fetchone()
            if final is None or final['id'] in required:
                raise ValueError('scope requires one separate final task')
            for task in required:
                if not self.db.execute('SELECT 1 FROM tasks WHERE id=?', (task,)).fetchone():
                    raise ValueError('unknown required task')
                # A supporting task cannot depend, even indirectly, on the final task.
                if self.db.execute('WITH RECURSIVE deps(id) AS (SELECT dependency FROM dependencies WHERE task=? UNION SELECT dependency FROM dependencies JOIN deps ON task=deps.id) SELECT 1 FROM deps WHERE id=?', (task, final['id'])).fetchone():
                    raise ValueError('scope dependency cycle')
            for row in self.db.execute("SELECT required FROM scopes WHERE state IN ('accepted','pending','rejected')"):
                if not set(json.loads(row['required'])).issubset(required):
                    raise ValueError('critical work cannot be dropped')
            ident = uuid.uuid4().hex
            self.db.execute('INSERT INTO scopes(id,author,base_version,required) VALUES(?,?,?,?)', (ident, author, base_version, json.dumps(sorted(required))))
            self.event(author, 'scope_proposed', {'proposal_id': ident, 'required': sorted(required), 'base_version': base_version})
            return ident

    def review_scope(self, proposal_id: str, reviewer: str, approve: bool, reason: str) -> int:
        if type(approve) is not bool or not reason.strip():
            raise ValueError('review needs decision and reason')
        with self.transaction():
            self.active_peer(reviewer)
            row = self.db.execute('SELECT * FROM scopes WHERE id=?', (proposal_id,)).fetchone()
            if self.closed or row is None or row['author'] == reviewer or row['state'] != 'pending' or row['base_version'] != self.scope_version:
                raise ValueError('independent current scope review required')
            version = self.scope_version
            if approve:
                required = set(json.loads(row['required']))
                for other in self.db.execute("SELECT required FROM scopes WHERE state IN ('pending','rejected','accepted')"):
                    if not set(json.loads(other['required'])).issubset(required):
                        raise ValueError('critical work unresolved')
                version += 1
                self.db.execute("UPDATE meta SET value=? WHERE key='scope_version'", (str(version),))
                final = self.db.execute('SELECT id FROM tasks WHERE final=1').fetchone()[0]
                self.db.execute('DELETE FROM dependencies WHERE task=?', (final,))
                self.db.executemany('INSERT INTO dependencies VALUES(?,?)', [(final, t) for t in required])
                self.db.execute("UPDATE scopes SET state='superseded' WHERE state IN ('pending','rejected','accepted') AND id!=?", (proposal_id,))
                # Invalidate any final claim or previously published final artifact.
                self.db.execute("UPDATE tasks SET state='open',holder=NULL,token=NULL,expires=NULL WHERE id=?", (final,))
            self.db.execute('UPDATE scopes SET state=?,reviewer=?,reason=?,accepted_version=? WHERE id=?', ('accepted' if approve else 'rejected', reviewer, reason, version if approve else None, proposal_id))
            self.event(reviewer, 'scope_reviewed', {'proposal_id': proposal_id, 'approved': approve, 'scope_version': version, 'reason': reason})
            return version

    def completion_snapshot(self) -> CompletionSnapshot | None:
        if not self.scope_version or self.unresolved_scope():
            return None
        final = self.db.execute('SELECT id,state FROM tasks WHERE final=1').fetchone()
        if final is None or final['state'] != 'approved':
            return None
        scope = self.db.execute("SELECT required FROM scopes WHERE state='accepted' AND accepted_version=?", (self.scope_version,)).fetchone()
        if scope is None:
            return None
        ids = []
        for task in [*json.loads(scope[0]), final['id']]:
            row = self.db.execute("SELECT a.id FROM artifacts a JOIN tasks t ON t.id=a.task WHERE t.id=? AND t.state='approved' AND a.approved=1 ORDER BY a.version DESC LIMIT 1", (task,)).fetchone()
            if row is None:
                return None
            if task == final['id'] and self.db.execute('SELECT scope_version FROM artifacts WHERE id=?', (row['id'],)).fetchone()[0] != self.scope_version:
                return None
            ids.append(row['id'])
        return CompletionSnapshot(self.scope_version, tuple(ids))

    def snapshot_current(self, snapshot: CompletionSnapshot) -> bool:
        return snapshot is not None and self.completion_snapshot() == snapshot
