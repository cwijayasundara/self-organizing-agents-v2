import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
from .demo import replay
from .models.live import validate_live_config,LiveUnavailable


def main():
    parser=argparse.ArgumentParser(prog='agora-v2')
    sub=parser.add_subparsers(dest='command',required=True)
    replay_parser=sub.add_parser('replay',help='Run explicitly scripted offline transitions')
    replay_parser.add_argument('--out',type=Path,required=True)
    inspect=sub.add_parser('inspect')
    inspect.add_argument('path',type=Path)
    run=sub.add_parser('run',help='Validate opt-in live configuration; integration currently gated')
    run.add_argument('--mission',type=Path,required=True)
    run.add_argument('--models',type=Path,required=True)
    run.add_argument('--budget-usd',type=float)
    run.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='run':
        try:
            validate_live_config(json.loads(args.models.read_text()),args.budget_usd)
        except (ValueError,LiveUnavailable,OSError) as exc:
            parser.error(str(exc))
    if args.command=='replay':
        result=asyncio.run(replay(args.out))
        print(json.dumps({'mode':'scripted','synthetic_cost':True,**asdict(result)}))
        return 0 if result.status=='completed' else 1
    trace=args.path/'trace.json' if args.path.is_dir() else args.path
    print(trace.read_text())
    return 0
