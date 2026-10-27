import asyncio
import pytest
from agora_v2.slots import ExecutionSlots


async def test_parent_yields_and_leaf_cannot_recurse():
    slots=ExecutionSlots(1)
    async with slots.enter('peer','p') as parent:
        async with parent.yield_to_child():
            async with slots.enter('leaf','child') as leaf:
                assert slots.active==1
                with pytest.raises(ValueError):
                    async with leaf.yield_to_child():
                        pass
        assert slots.active==1
    assert slots.active==0 and slots.peak==1


async def test_cancel_reacquisition_leaks_no_slot():
    slots=ExecutionSlots(1)
    held=asyncio.Event()
    release=asyncio.Event()
    async def child():
        async with slots.enter('leaf','child'):
            held.set()
            await release.wait()
    async def parent():
        async with slots.enter('peer','p') as execution:
            async with execution.yield_to_child():
                asyncio.create_task(child())
                await held.wait()
    p=asyncio.create_task(parent())
    await held.wait()
    await asyncio.sleep(0)
    p.cancel()
    with pytest.raises(asyncio.CancelledError):
        await p
    release.set()
    await asyncio.sleep(0)
    assert slots.active==0


async def test_global_context_peak():
    slots=ExecutionSlots(5)
    async def work(i):
        async with slots.enter('peer' if i%2 else 'leaf',str(i)):
            await asyncio.sleep(.001)
    await asyncio.gather(*(work(i) for i in range(20)))
    assert slots.peak==5 and slots.active==0
