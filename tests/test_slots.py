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


async def test_cancellation_in_child_does_not_wait_for_unrelated_slot():
    slots=ExecutionSlots(1)
    occupied=asyncio.Event()
    release=asyncio.Event()
    unrelated_task=None
    async def unrelated():
        async with slots.enter('peer','other'):
            occupied.set()
            await release.wait()
    async def parent():
        nonlocal unrelated_task
        async with slots.enter('peer','parent') as ex:
            async with ex.yield_to_child():
                unrelated_task=asyncio.create_task(unrelated())
                await occupied.wait()
                raise asyncio.CancelledError()
    task=asyncio.create_task(parent())
    try:
        await occupied.wait()
        done,_=await asyncio.wait({task},timeout=.05)
        assert task in done, 'cancelled parent waits to reacquire an unrelated slot'
        assert task.cancelled()
    finally:
        release.set()
        await asyncio.gather(task,return_exceptions=True)
        if unrelated_task:
            await unrelated_task
    assert slots.active==0
