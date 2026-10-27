import asyncio
import json
import threading
from urllib.request import urlopen,Request
from urllib.error import HTTPError
import pytest
from agora_v2.demo import replay
from agora_v2.observer import make_server,read_snapshot


def test_observer_serves_trace_without_mutations(tmp_path):
    asyncio.run(replay(tmp_path/'run'))
    server=make_server(tmp_path/'run',0)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        trace=json.load(urlopen(base+'/api/snapshot'))
        assert trace['mode']=='scripted' and trace['status']=='completed'
        events=json.load(urlopen(base+'/api/events?after=10'))
        assert events and all(e['seq']>10 for e in events)
        assert '<script src="/app.js"' in urlopen(base).read().decode()
        for path,method in [('/api/snapshot','POST'),('/../eval/gold/evidence_review.json','GET')]:
            with pytest.raises(HTTPError) as exc:
                urlopen(Request(base+path,method=method))
            assert exc.value.code in (404,405)
        assert json.load(urlopen(base+'/api/snapshot'))['events']==trace['events']
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_active_database_observation_does_not_initialize_or_mutate(tmp_path):
    from agora_v2.demo import build_runtime
    runtime=build_runtime(tmp_path/'run')
    before=runtime.ledger.events()
    data=read_snapshot(tmp_path/'run')
    assert len(data['peers'])==3
    assert runtime.ledger.events()==before
    runtime.ledger.close()


def test_completed_database_snapshot_has_persisted_status_and_memo(tmp_path):
    asyncio.run(replay(tmp_path/'run'))
    data=read_snapshot(tmp_path/'run/run.db')
    assert data['status']=='completed'
    assert 'RESEARCH_SUMMARY' in data['final_memo']
