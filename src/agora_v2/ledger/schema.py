SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO meta VALUES('schema_version','1'),('scope_version','0'),('closed','0');
CREATE TABLE IF NOT EXISTS peers(id TEXT PRIMARY KEY, family TEXT NOT NULL, model_key TEXT NOT NULL DEFAULT '', state TEXT NOT NULL, bootstrap INTEGER NOT NULL, capability TEXT NOT NULL DEFAULT 'general');
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, key TEXT NOT NULL UNIQUE, spec TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'open', final INTEGER NOT NULL DEFAULT 0, holder TEXT REFERENCES peers(id), token TEXT, expires REAL, repairs INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS dependencies(task TEXT REFERENCES tasks(id), dependency TEXT REFERENCES tasks(id), PRIMARY KEY(task,dependency), CHECK(task != dependency));
CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, task TEXT REFERENCES tasks(id), author TEXT REFERENCES peers(id), content TEXT NOT NULL, evidence TEXT NOT NULL, version INTEGER NOT NULL, approved INTEGER NOT NULL DEFAULT 0, UNIQUE(task,version));
CREATE TABLE IF NOT EXISTS reviews(artifact TEXT REFERENCES artifacts(id), reviewer TEXT REFERENCES peers(id), approved INTEGER NOT NULL, reason TEXT NOT NULL, PRIMARY KEY(artifact,reviewer));
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, time REAL NOT NULL, actor TEXT NOT NULL, type TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TABLE IF NOT EXISTS scopes(id TEXT PRIMARY KEY, author TEXT REFERENCES peers(id), base_version INTEGER NOT NULL, required TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', reviewer TEXT, reason TEXT, accepted_version INTEGER);
CREATE TABLE IF NOT EXISTS helper_proposals(id TEXT PRIMARY KEY, requester TEXT REFERENCES peers(id), proposal TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', reviewer TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, peer TEXT NOT NULL, purpose TEXT NOT NULL, reserved INTEGER NOT NULL, settled INTEGER, state TEXT NOT NULL, usage TEXT);
'''
