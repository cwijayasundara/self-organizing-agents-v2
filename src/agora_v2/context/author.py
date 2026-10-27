"""Pinned authors' RLM engine, isolated with host-controlled model dispatch."""
from dataclasses import asdict
import json
import uuid
from .docker import DockerExecutor
from .bridge import SemanticBridge
from ..models import ModelRequest

AUTHOR_REVISION = 'd04208afbad29ca675ab13478c40ee8bebc84bfe'
AUTHOR_IMAGE = 'agora-v2-rlms:' + AUTHOR_REVISION[:12]


class AuthorBridge(SemanticBridge):
    def __init__(self, store, gateway, slots, handles, root_model, leaf_model, max_output_tokens):
        super().__init__(store, gateway, slots, handles)
        self.root_model, self.leaf_model = root_model, leaf_model
        self.max_output_tokens = max_output_tokens

    async def dispatch(self, message, execution):
        if isinstance(message, dict) and message.get('op') == 'author_call':
            kind = message.get('kind')
            if kind not in ('root', 'leaf'):
                raise ValueError('unknown author call role')
            # Model aliases in generated code cannot choose an ungranted provider.
            model = self.root_model if kind == 'root' else self.leaf_model
            prompt = message.get('prompt')
            text = prompt if isinstance(prompt, str) else json.dumps(prompt, ensure_ascii=False)
            if not isinstance(text, str):
                raise ValueError('invalid author prompt')
            messages = tuple(prompt) if isinstance(prompt, list) else None
            request = ModelRequest(model, text, self.max_output_tokens, messages=messages)
            purpose = getattr(execution, 'purpose', 'exploration')
            if kind == 'root':
                response = await self.gateway.call(request, purpose, execution)
            else:
                if execution.kind != 'peer' or not execution.held:
                    raise ValueError('semantic recursion depth exceeded')
                identity = execution.identity + ':leaf:' + uuid.uuid4().hex
                self.gateway.budget.ledger.event(execution.identity, 'semantic_call_started', {'identity': identity, 'engine': 'authors-rlms', 'model_key': model})
                async with execution.yield_to_child():
                    async with self.slots.enter('leaf', identity) as child:
                        child.billing_identity = execution.identity
                        response = await self.gateway.call(request, purpose, child)
                self.gateway.budget.ledger.event(execution.identity, 'semantic_call_finished', {'identity': identity, 'engine': 'authors-rlms'})
            return asdict(response)
        return await super().dispatch(message, execution)


class AuthorRLMExecutor(DockerExecutor):
    def __init__(self, store, gateway, slots, image=AUTHOR_IMAGE, timeout_seconds=120):
        super().__init__(store, gateway, slots, image, timeout_seconds)

    async def reason(self, model_key, prompt, handles, execution, leaf_model=None, max_output_tokens=2000):
        leaf_model = leaf_model or model_key
        if model_key not in self.gateway.models or leaf_model not in self.gateway.models:
            raise ValueError('author adapter model is not allowlisted')
        evidence = {}
        for h in handles:
            _, refs = self.store.get(h)
            evidence[refs[0] if len(refs) == 1 and refs[0] not in evidence else h] = h
        bridge = AuthorBridge(self.store, self.gateway, self.slots, handles, model_key, leaf_model, max_output_tokens)
        config = {'prompt': prompt, 'evidence_handles': evidence, 'max_output_tokens': max_output_tokens, 'revision': AUTHOR_REVISION}
        return await self._run_worker(config, handles, execution, 'author_worker.py', bridge, memory='512m')


async def verify_author_image(image=AUTHOR_IMAGE):
    import asyncio
    from ..models.live import LiveUnavailable
    try:
        proc = await asyncio.create_subprocess_exec('docker', 'image', 'inspect', image, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        raw, _ = await asyncio.wait_for(proc.communicate(), 10)
        if proc.returncode != 0:
            raise ValueError('image missing')
        details = json.loads(raw)[0]
        if details['Config'].get('Labels', {}).get('ai.agora.rlm-revision') != AUTHOR_REVISION:
            raise ValueError('unverified image revision')
        return {'image': details['Id'], 'revision': AUTHOR_REVISION}
    except (OSError, ValueError, KeyError, IndexError, TimeoutError):
        raise LiveUnavailable('Verified author-package sandbox image unavailable. Build it explicitly with docker build -f sandbox/Dockerfile -t ' + AUTHOR_IMAGE + ' .')
