import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import threading

from .demo import replay
from .eval.runner import evaluate
from .live import run_live
from .mission import load_mission
from .observer import make_server
from .models.live import LiveUnavailable
from .smoke import run_smoke


def main():
    parser=argparse.ArgumentParser(prog='agora-v2')
    sub=parser.add_subparsers(dest='command',required=True)
    replay_parser=sub.add_parser('replay',help='Run explicitly scripted offline transitions')
    replay_parser.add_argument('--out',type=Path,required=True)
    inspect=sub.add_parser('inspect');inspect.add_argument('path',type=Path)
    run=sub.add_parser('run',help='Run autonomous GLM/DeepSeek peers with isolated authors RLM')
    run.add_argument('--mission',type=Path,required=True)
    run.add_argument('--models',type=Path,required=True)
    run.add_argument('--budget-usd',type=float,required=True)
    run.add_argument('--out',type=Path,required=True)
    run.add_argument('--watch',action='store_true',help='Keep a read-only live observer open until Ctrl-C')
    run.add_argument('--port',type=int,default=8765)
    smoke=sub.add_parser('smoke',help='Explicitly capped live usage and semantic-subcall verification')
    smoke.add_argument('--models',type=Path,required=True)
    smoke.add_argument('--budget-usd',type=float,required=True)
    smoke.add_argument('--out',type=Path,required=True)
    observe=sub.add_parser('observe',help='Serve a read-only run observer')
    observe.add_argument('path',type=Path);observe.add_argument('--port',type=int,default=8765)
    evaluation=sub.add_parser('evaluate',help='Score exports or execute matched architectures and repetitions')
    evaluation.add_argument('--config',type=Path,required=True)
    evaluation.add_argument('--out',type=Path,required=True)
    evaluation.add_argument('--budget-usd',type=float,help='Explicit TOTAL cap across all executed arms and seeds')
    args=parser.parse_args()
    server=None;thread=None
    def started(runtime):
        nonlocal server,thread
        server=make_server(runtime.output,args.port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        print(f'Read-only live observer: http://127.0.0.1:{server.server_port}',flush=True)
    try:
        if args.command=='evaluate':
            report=asyncio.run(evaluate(args.config,args.out,budget_usd=args.budget_usd))
            print(json.dumps(report,indent=2))
            return 0
        if args.command=='smoke':
            report=asyncio.run(run_smoke(json.loads(args.models.read_text()),args.budget_usd,args.out))
            print(json.dumps(report,indent=2))
            return 0 if report['status']=='completed' else 1
        if args.command=='run':
            result=asyncio.run(run_live(load_mission(args.mission),json.loads(args.models.read_text()),args.budget_usd,args.out,on_started=started if args.watch else None))
            print(json.dumps(asdict(result)),flush=True)
            if thread is not None:
                print('Run finished; observer remains available. Ctrl-C stops the observer.',flush=True)
                thread.join()
            return 0 if result.status=='completed' else 1
        if args.command=='observe':
            server=make_server(args.path,args.port)
            print(f'Read-only observer: http://127.0.0.1:{server.server_port}',flush=True)
            server.serve_forever()
            return 0
        if args.command=='replay':
            result=asyncio.run(replay(args.out))
            print(json.dumps({'mode':'scripted','synthetic_cost':True,**asdict(result)}))
            return 0 if result.status=='completed' else 1
        trace=args.path/'trace.json' if args.path.is_dir() else args.path
        print(trace.read_text());return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError,LiveUnavailable,OSError) as exc:
        parser.error(str(exc))
    finally:
        if server is not None:
            if thread is not None:server.shutdown()
            server.server_close()
