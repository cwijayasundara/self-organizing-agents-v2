import asyncio
import json
from pathlib import Path
import uuid
from .bridge import SemanticBridge


class DockerExecutor:
    """No host exec fallback; container image must be explicitly provisioned."""
    def __init__(self, store, gateway, slots, image='python:3.12-slim', timeout_seconds=30,allow_semantic=True):
        self.store, self.gateway, self.slots, self.image, self.timeout_seconds = store, gateway, slots, image, timeout_seconds
        self.allow_semantic=allow_semantic
        self.containers = set()

    async def execute(self, code: str, handles: list[str], execution):
        if not isinstance(code, str) or len(code.encode()) > 50000:
            raise ValueError('unbounded code')
        return await self._run_worker({'code': code}, handles, execution, 'worker.py', SemanticBridge(self.store, self.gateway, self.slots, handles,self.allow_semantic))

    async def _run_worker(self, config, handles, execution, worker_name, bridge, memory='128m'):
        if not isinstance(handles, list) or len(handles) > 50:
            raise ValueError('unbounded handles')
        if execution.kind != 'peer' or not execution.held:
            raise ValueError('only peers can execute context programs')
        name = 'agora-v2-' + uuid.uuid4().hex
        worker = Path(__file__).with_name(worker_name).resolve()
        args = ['docker', 'run', '--rm', '--pull=never', '--name', name, '-i', '--network=none', '--read-only', '--user', '65534:65534', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit=32', '--memory='+memory, '--cpus=1', '--tmpfs', '/scratch:rw,noexec,nosuid,size=16m,mode=1777', '--mount', f'type=bind,src={worker},dst=/worker.py,readonly', '--workdir', '/scratch', self.image, 'python', '-I', '-B', '/worker.py']
        proc = None
        self.containers.add(name)

        async def run():
            nonlocal proc
            proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=1100000)
            proc.stdin.write((json.dumps(config) + '\n').encode())
            await proc.stdin.drain()
            total = 0
            for _ in range(100):
                line = await proc.stdout.readline()
                total += len(line)
                if total > 4000000 or len(line) > 1100000:
                    raise RuntimeError('container protocol output limit')
                if not line:
                    raise RuntimeError('container exited without result; image/runtime unavailable or code failed')
                msg = json.loads(line)
                if msg.get('op') == 'error':
                    raise RuntimeError(msg.get('error', 'isolated code failed'))
                result = await bridge.dispatch(msg, execution)
                if msg['op'] == 'result':
                    proc.stdin.close()
                    await proc.wait()
                    if proc.returncode != 0:
                        raise RuntimeError('container failed after result')
                    return result
                proc.stdin.write((json.dumps(result) + '\n').encode())
                await proc.stdin.drain()
            raise RuntimeError('bridge operation limit')
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await run()
        finally:
            await self._remove(name)
            if proc is not None and proc.returncode is None:
                proc.kill()
                await proc.wait()

    async def _remove(self, name):
        proc = await asyncio.create_subprocess_exec('docker', 'rm', '-f', name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.wait_for(proc.wait(), 10)
        if proc.returncode != 0:
            check = await asyncio.create_subprocess_exec('docker', 'inspect', name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await check.wait()
            if check.returncode == 0:
                raise RuntimeError('container cleanup failed')
        self.containers.discard(name)

    async def close(self):
        for name in list(self.containers):
            await self._remove(name)
