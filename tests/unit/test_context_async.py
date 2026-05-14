"""Tests for tenantshield.context (asynchronous API)."""

from __future__ import annotations

import asyncio

import pytest

from tenantshield._types import TenantId
from tenantshield.context import (
    atenant_scope,
    bind_tenant,
    current_tenant,
    try_current_tenant,
)


@pytest.mark.asyncio
async def test_atenant_scope_binds_and_releases() -> None:
    ctx = bind_tenant(TenantId("acme"))
    async with atenant_scope(ctx):
        assert current_tenant() is ctx
    assert try_current_tenant() is None


@pytest.mark.asyncio
async def test_atenant_scope_nested() -> None:
    outer = bind_tenant(TenantId("outer"))
    inner = bind_tenant(TenantId("inner"))
    async with atenant_scope(outer):
        assert current_tenant() is outer
        async with atenant_scope(inner):
            assert current_tenant() is inner
        assert current_tenant() is outer
    assert try_current_tenant() is None


@pytest.mark.asyncio
async def test_atenant_scope_exception_releases() -> None:
    ctx = bind_tenant(TenantId("acme"))

    class _BoomError(Exception):
        pass

    with pytest.raises(_BoomError):
        async with atenant_scope(ctx):
            raise _BoomError

    assert try_current_tenant() is None


@pytest.mark.asyncio
async def test_atenant_scope_propagation_to_create_task() -> None:
    """contextvars propagate to child tasks via asyncio.create_task."""
    seen: list[TenantId] = []

    async def child() -> None:
        seen.append(current_tenant().tenant_id)

    async with atenant_scope(bind_tenant(TenantId("acme"))):
        task = asyncio.create_task(child())
        await task

    assert seen == ["acme"]


@pytest.mark.asyncio
async def test_atenant_scope_propagation_to_gather() -> None:
    """contextvars propagate through asyncio.gather to concurrent coroutines."""

    async def read_tenant() -> TenantId:
        return current_tenant().tenant_id

    async with atenant_scope(bind_tenant(TenantId("acme"))):
        results = await asyncio.gather(read_tenant(), read_tenant())

    assert results == ["acme", "acme"]


@pytest.mark.asyncio
async def test_atenant_scope_propagation_to_task_group() -> None:
    """contextvars propagate to TaskGroup tasks (Python 3.11+)."""
    seen: list[TenantId] = []

    async def child() -> None:
        seen.append(current_tenant().tenant_id)

    async with (
        atenant_scope(bind_tenant(TenantId("acme"))),
        asyncio.TaskGroup() as tg,
    ):
        tg.create_task(child())
        tg.create_task(child())

    assert seen == ["acme", "acme"]


@pytest.mark.asyncio
async def test_atenant_scope_propagates_to_thread() -> None:
    """asyncio.to_thread propagates contextvars by default in Python 3.11+."""

    def in_thread() -> TenantId:
        return current_tenant().tenant_id

    async with atenant_scope(bind_tenant(TenantId("acme"))):
        tid = await asyncio.to_thread(in_thread)
        assert tid == "acme"
