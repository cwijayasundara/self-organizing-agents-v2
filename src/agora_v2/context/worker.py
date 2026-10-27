"""Executed only inside the configured container, never on the host."""
import contextlib
import io
import json
import sys

wire_in=sys.stdin
wire_out=sys.stdout


def rpc(op, **fields):
    wire_out.write(json.dumps({'op':op,**fields})+'\n')
    wire_out.flush()
    response=json.loads(wire_in.readline())
    if 'error' in response:
        raise RuntimeError(response['error'])
    return response


class BoundedOutput(io.TextIOBase):
    def __init__(self):
        self.size=0
    def write(self,text):
        self.size+=len(text)
        if self.size>10000:
            raise RuntimeError('generated output limit exceeded')
        return len(text)


def read_context(handle):
    return rpc('read_context',handle=handle)['value']


def semantic_call(model_key,handles,instruction,max_output_tokens=1000):
    return rpc('semantic_call',model_key=model_key,handles=handles,instruction=instruction,max_output_tokens=max_output_tokens)


def store_value(value,source_handles=()):
    return rpc('store',value=value,source_handles=list(source_handles))['handle']


try:
    config=json.loads(wire_in.readline())
    scope={'read_context':read_context,'semantic_call':semantic_call,'store_value':store_value}
    with contextlib.redirect_stdout(BoundedOutput()),contextlib.redirect_stderr(BoundedOutput()):
        exec(compile(config['code'],'<isolated-peer>','exec'),scope,scope)
    handle=scope.get('RESULT')
    if not isinstance(handle,str):
        raise ValueError('code must set RESULT to a stored context handle')
    wire_out.write(json.dumps({'op':'result','handle':handle})+'\n')
    wire_out.flush()
except BaseException as exc:
    wire_out.write(json.dumps({'op':'error','error':f'{type(exc).__name__}: {str(exc)[:500]}'})+'\n')
    wire_out.flush()
    sys.exit(1)
