from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time

from .scope import Scope, CompletionSnapshot
from .schema import SCHEMA
from .tasks import Task, TaskSpec, Claim, ClaimResult, Tasks
from .artifacts import Artifact, Artifacts


class Ledger(Tasks, Artifacts, Scope):
    def __init__(self, path: Path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript(SCHEMA)
        if 'scope_version' not in {r[1] for r in self.db.execute('PRAGMA table_info(artifacts)')}:
            self.db.execute('ALTER TABLE artifacts ADD COLUMN scope_version INTEGER NOT NULL DEFAULT 0')
        self.db.execute("UPDATE meta SET value='2' WHERE key='schema_version'")

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def event(self, actor: str, kind: str, payload: dict):
        self.db.execute('INSERT INTO events(time,actor,type,payload) VALUES(?,?,?,?)', (self.clock(), actor, kind, json.dumps(payload, allow_nan=False)))

    def events(self, after: int = 0) -> list[dict]:
        return [{**dict(r), 'payload': json.loads(r['payload'])} for r in self.db.execute('SELECT * FROM events WHERE seq>? ORDER BY seq', (after,))]

    @property
    def closed(self):
        return self.db.execute("SELECT value FROM meta WHERE key='closed'").fetchone()[0] == '1'

    @property
    def scope_version(self):
        return int(self.db.execute("SELECT value FROM meta WHERE key='scope_version'").fetchone()[0])

    def unresolved_scope(self):
        return bool(self.db.execute("SELECT 1 FROM scopes WHERE state IN ('pending','rejected')").fetchone())

    def register_peer(self, peer_id: str, family: str, model_key: str = '', bootstrap: bool = True, capability: str = 'general'):
        with self.transaction():
            if self.closed:
                raise ValueError('admission closed')
            self.db.execute("INSERT INTO peers VALUES(?,?,?,'ready',?,?)", (peer_id, family, model_key, bootstrap, capability))
            self.event(peer_id, 'peer_joined', {'family': family, 'bootstrap': bootstrap, 'capability': capability})

    def active_peer(self, peer_id: str):
        row = self.db.execute('SELECT * FROM peers WHERE id=?', (peer_id,)).fetchone()
        if row is None or row['state'] in ('retired', 'failed', 'draining'):
            raise ValueError('inactive or unknown peer')
        return row

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
