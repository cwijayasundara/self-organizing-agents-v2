"""Trusted adapter bootstrap. Runs exclusively in the pinned author image."""
import asyncio
import contextlib
import io
import json
import sys
import threading

wire_in, wire_out = sys.stdin, sys.stdout
wire_lock = threading.RLock()


def rpc(op, **fields):
    with wire_lock:
        wire_out.write(json.dumps({'op': op, **fields}) + '\n')
        wire_out.flush()
        line = wire_in.readline()
        if not line:
            raise RuntimeError('host bridge closed')
        result = json.loads(line)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result


class BoundedOutput(io.TextIOBase):
    def __init__(self): self.size = 0
    def write(self, value):
        self.size += len(value)
        if self.size > 20000:
            raise RuntimeError('author interpreter output limit')
        return len(value)


def run(config):
    from pathlib import Path
    if Path('/opt/agora-rlms-revision').read_text().strip() != config['revision']:
        raise RuntimeError('author package revision mismatch')
    import rlm.core.rlm as core
    from rlm.clients.base_lm import BaseLM
    from rlm.core.types import ModelUsageSummary, UsageSummary

    class GatewayLM(BaseLM):
        def __init__(self, kind):
            super().__init__(model_name=kind)
            self.kind = kind
            self.calls = self.inputs = self.outputs = 0
            self.last = ModelUsageSummary(0, 0, 0)

        def completion(self, prompt):
            kind = 'root' if self.kind == 'root' and threading.current_thread() is threading.main_thread() else 'leaf'
            result = rpc('author_call', kind=kind, prompt=prompt)
            self.last = ModelUsageSummary(1, result['input_tokens'], result['output_tokens'])
            self.calls += 1
            self.inputs += result['input_tokens']
            self.outputs += result['output_tokens']
            return result['content']

        async def acompletion(self, prompt):
            return await asyncio.to_thread(self.completion, prompt)

        def get_last_usage(self): return self.last
        def get_usage_summary(self):
            return UsageSummary({self.kind: ModelUsageSummary(self.calls, self.inputs, self.outputs)})

    def client_factory(backend, kwargs):
        return GatewayLM(kwargs['model_name'])

    # Version-pinned backend seam: no provider client or credential is constructed.
    core.get_client = client_factory
    context = {'evidence': {ref: rpc('read_context', handle=h)['value'] for ref, h in config['evidence_handles'].items()}}
    engine = core.RLM(backend='openai', backend_kwargs={'model_name': 'root'},
                      other_backends=['openai'], other_backend_kwargs=[{'model_name': 'leaf'}],
                      environment='local', depth=0, max_depth=1, max_iterations=8,
                      max_concurrent_subcalls=4, verbose=False)
    try:
        result = engine.completion(context, root_prompt=config['prompt'])
        return rpc('store', value=result.response, source_handles=list(config['evidence_handles'].values()))['handle']
    finally:
        if hasattr(engine, 'close'): engine.close()


try:
    config = json.loads(wire_in.readline())
    with contextlib.redirect_stdout(BoundedOutput()), contextlib.redirect_stderr(BoundedOutput()):
        handle = run(config)
    wire_out.write(json.dumps({'op': 'result', 'handle': handle}) + '\n')
    wire_out.flush()
except BaseException as exc:
    wire_out.write(json.dumps({'op': 'error', 'error': f'{type(exc).__name__}: {str(exc)[:500]}'}) + '\n')
    wire_out.flush()
    sys.exit(1)
