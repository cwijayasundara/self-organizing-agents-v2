from dataclasses import dataclass
import json
import uuid


@dataclass(frozen=True)
class Artifact:
    id: str
    task_id: str
    author: str
    content: str
    version: int


class Artifacts:
    def publish(self, claim, content: str, evidence: list[str]) -> Artifact:
        if not isinstance(content, str) or not content.strip() or len(content) > 100000:
            raise ValueError('invalid artifact')
        if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
            raise ValueError('invalid evidence references')
        with self.transaction():
            self.check_claim(claim)
            version = self.db.execute('SELECT COALESCE(MAX(version),0)+1 FROM artifacts WHERE task=?', (claim.task_id,)).fetchone()[0]
            result = Artifact(uuid.uuid4().hex, claim.task_id, claim.peer_id, content, version)
            self.db.execute('INSERT INTO artifacts(id,task,author,content,evidence,version,scope_version) VALUES(?,?,?,?,?,?,?)', (result.id, claim.task_id, claim.peer_id, content, json.dumps(evidence), version, self.scope_version))
            self.db.execute("UPDATE tasks SET state='published',holder=NULL,token=NULL,expires=NULL WHERE id=?", (claim.task_id,))
            self.event(claim.peer_id, 'artifact_published', {'artifact_id': result.id, 'task_id': claim.task_id, 'version': version, 'evidence': evidence})
            return result

    def review_artifact(self, artifact_id: str, reviewer: str, approve: bool, reason: str):
        if type(approve) is not bool or not reason.strip():
            raise ValueError('review requires a decision and reason')
        with self.transaction():
            self.active_peer(reviewer)
            row = self.db.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone()
            if row is None or row['author'] == reviewer:
                raise ValueError('independent review required')
            task = self.db.execute('SELECT state,final FROM tasks WHERE id=?', (row['task'],)).fetchone()
            if task['state'] != 'published' or (task['final'] and row['scope_version'] != self.scope_version):
                raise ValueError('stale or no longer published artifact')
            latest = self.db.execute('SELECT MAX(version) FROM artifacts WHERE task=?', (row['task'],)).fetchone()[0]
            if latest != row['version']:
                raise ValueError('stale artifact review')
            self.db.execute('INSERT INTO reviews VALUES(?,?,?,?)', (artifact_id, reviewer, approve, reason))
            self.db.execute('UPDATE artifacts SET approved=? WHERE id=?', (approve, artifact_id))
            self.db.execute('UPDATE tasks SET state=? WHERE id=?', ('approved' if approve else 'open', row['task']))
            self.event(reviewer, 'artifact_reviewed', {'artifact_id': artifact_id, 'approved': approve, 'reason': reason})
