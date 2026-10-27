import asyncio
from contextlib import asynccontextmanager


class Execution:
    def __init__(self, pool, kind, identity):
        self.pool, self.kind, self.identity = pool, kind, identity
        self.held = False

    async def acquire(self):
        await self.pool.semaphore.acquire()
        self.held = True
        self.pool.active += 1
        self.pool.peak = max(self.pool.peak,self.pool.active)

    def release(self):
        if self.held:
            self.held = False
            self.pool.active -= 1
            self.pool.semaphore.release()

    @asynccontextmanager
    async def yield_to_child(self):
        if self.kind != 'peer' or not self.held:
            raise ValueError('only an executing peer can create a semantic leaf')
        self.release()
        try:
            yield
        finally:
            # If cancellation happens here enter() still owns cleanup, without
            # releasing a permit the parent never reacquired.
            await self.acquire()


class ExecutionSlots:
    def __init__(self, capacity: int):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('invalid capacity')
        self.semaphore = asyncio.Semaphore(capacity)
        self.active = self.peak = 0
        self.identities = set()

    @asynccontextmanager
    async def enter(self, kind: str, identity: str):
        if kind not in ('peer','leaf') or identity in self.identities:
            raise ValueError('invalid or duplicate execution context')
        self.identities.add(identity)
        ex = Execution(self,kind,identity)
        try:
            await ex.acquire()
            yield ex
        finally:
            ex.release()
            self.identities.remove(identity)
