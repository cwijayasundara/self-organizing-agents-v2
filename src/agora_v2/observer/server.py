from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit,parse_qs


def read_snapshot(path: Path):
    path=Path(path).resolve()
    trace=path/'trace.json' if path.is_dir() else path
    if trace.is_file() and trace.suffix=='.json':
        return json.loads(trace.read_text())
    dbpath=path/'run.db' if path.is_dir() else path
    db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True,isolation_level=None)
    db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN')
        result={name:[dict(r) for r in db.execute(f'SELECT * FROM {name}')] for name in ('peers','tasks','artifacts','scopes','helper_proposals','calls')}
        result['events']=[{**dict(r),'payload':json.loads(r['payload'])} for r in db.execute('SELECT * FROM events ORDER BY seq')]
        metadata=dict(db.execute('SELECT key,value FROM meta'))
        result.update({'format_version':1,'mode':metadata.get('mode','unknown'),'status':'running','final_memo':''})
        return result
    finally:
        db.close()


def make_server(path: Path,port: int=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def do_GET(self):
            url=urlsplit(self.path)
            try:
                if url.path=='/api/snapshot':
                    payload=json.dumps(read_snapshot(path)).encode()
                    mime='application/json'
                elif url.path=='/api/events':
                    after=int(parse_qs(url.query).get('after',['0'])[0])
                    payload=json.dumps([e for e in read_snapshot(path)['events'] if e['seq']>after]).encode()
                    mime='application/json'
                else:
                    names={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
                    if url.path not in names:
                        self.send_error(404)
                        return
                    name=names[url.path]
                    payload=files('agora_v2').joinpath('web',name).read_bytes()
                    mime={'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[name]
                self.send_response(200)
                self.send_header('Content-Type',mime+'; charset=utf-8')
                self.send_header('Content-Length',str(len(payload)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(payload)
            except (OSError,ValueError,sqlite3.Error) as exc:
                self.send_error(400,'Run unavailable or invalid request')

        def do_POST(self):self.send_error(405)
        def do_PUT(self):self.send_error(405)
        def do_PATCH(self):self.send_error(405)
        def do_DELETE(self):self.send_error(405)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)
