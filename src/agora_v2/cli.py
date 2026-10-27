import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
from .demo import replay


def main():
    parser=argparse.ArgumentParser(prog='agora-v2')
    sub=parser.add_subparsers(dest='command',required=True)
    replay_parser=sub.add_parser('replay',help='Run explicitly scripted offline transitions')
    replay_parser.add_argument('--out',type=Path,required=True)
    inspect=sub.add_parser('inspect')
    inspect.add_argument('path',type=Path)
    args=parser.parse_args()
    if args.command=='replay':
        result=asyncio.run(replay(args.out))
        print(json.dumps({'mode':'scripted','synthetic_cost':True,**asdict(result)}))
        return 0 if result.status=='completed' else 1
    trace=args.path/'trace.json' if args.path.is_dir() else args.path
    print(trace.read_text())
    return 0
