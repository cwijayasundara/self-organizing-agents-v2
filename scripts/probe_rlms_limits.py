"""Probe upstream limit method with fake usage, without installing providers.

This exercises one extracted upstream method, not a complete RLM adapter.
Run: python scripts/probe_rlms_limits.py /path/to/rlm-checkout
"""
import ast
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def probe(checkout):
    path=Path(checkout)/'rlm/core/rlm.py'
    tree=ast.parse(path.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RLM')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_check_iteration_limits')
    class LimitExceeded(Exception):
        def __init__(self,**kwargs):self.details=kwargs
    scope={'BudgetExceededError':LimitExceeded,'RLMIteration':object,'LMHandler':object}
    module=ast.Module(body=[method],type_ignores=[])
    exec(compile(ast.fix_missing_locations(module),str(path),'exec'),scope)
    logs=[]
    fake=SimpleNamespace(_consecutive_errors=0,_last_error=None,_best_partial_answer=None,max_errors=None,max_budget=.01,max_tokens=None,
                         verbose=SimpleNamespace(print_budget_exceeded=lambda *x:logs.append(x)))
    iteration=SimpleNamespace(code_blocks=[])
    # The public method consumes already incurred usage. Missing cost is treated
    # as zero by this upstream check; v2 must instead preserve liability.
    handler=SimpleNamespace(get_usage_summary=lambda:SimpleNamespace(total_cost=None))
    scope['_check_iteration_limits'](fake,iteration,0,handler)
    missing_cost_passed=True
    handler.get_usage_summary=lambda:SimpleNamespace(total_cost=.02)
    exceeded=False
    try:
        scope['_check_iteration_limits'](fake,iteration,0,handler)
    except LimitExceeded:
        exceeded=True
    return {'revision':subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip(),
            'probe':'extracted upstream _check_iteration_limits, fake usage only',
            'missing_cost_passed_limit_check':missing_cost_passed,'overspend_detected_after_usage':exceeded,
            'full_adapter_verified':False,'live_gate':'closed'}


if __name__=='__main__':
    print(json.dumps(probe(Path(sys.argv[1])),indent=2))
