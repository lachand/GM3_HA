"""Unit tests for coordinator.py: write-failure propagation and batched
polling (Family: coordinator, mocked device).

Builds PlumDataUpdateCoordinator via `object.__new__` instead of calling
its real `__init__`: `DataUpdateCoordinator.__init__` on the `homeassistant`
version this suite currently resolves calls `frame.report_usage`, which
raises `RuntimeError: Frame helper not set up` against this project's
lightweight `hass=MagicMock()` fixture (pre-existing gap, unrelated to
this diff -- see IMPROVEMENT_PLAN.md). Only the attributes
`_async_update_data`/`async_set_value`/`_perform_repeated_write` actually
touch are seeded: `device`, `available_slugs`, `_cache`, `_timestamps`,
`_cache_lock`, `ttl`. `async_set_updated_data` is stubbed out since it
belongs to the DataUpdateCoordinator base and isn't part of what's tested
here.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.plum_ecomax.coordinator import PlumDataUpdateCoordinator


@pytest.fixture(autouse=True)
def _no_real_sleeps(monkeypatch):
    """_perform_repeated_write sleeps 2s between each of its 5 attempts;
    without this the failure-path tests take ~8s each for no benefit.
    """
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(
        "custom_components.plum_ecomax.coordinator.asyncio.sleep", _instant_sleep
    )


def _make_coordinator(device=None, available_slugs=None, cache=None, timestamps=None, ttl=300):
    coordinator = object.__new__(PlumDataUpdateCoordinator)
    coordinator.device = device if device is not None else MagicMock()
    # _validate_value() does `self.device.params_map.get(slug, {})`; on a
    # bare MagicMock, .params_map and its .get() are themselves mocks, not
    # a real dict, which breaks the JSON-bounds comparisons downstream.
    if not isinstance(coordinator.device.params_map, dict):
        coordinator.device.params_map = {}
    coordinator.available_slugs = available_slugs if available_slugs is not None else []
    coordinator._cache = cache if cache is not None else {}
    coordinator._timestamps = timestamps if timestamps is not None else {}
    coordinator._cache_lock = asyncio.Lock()
    coordinator.ttl = ttl
    coordinator.async_set_updated_data = MagicMock()
    return coordinator


class TestWriteConfirmation:
    @pytest.mark.asyncio
    async def test_confirmed_on_first_attempt_marks_slug_stale_for_next_poll(self):
        device = MagicMock()
        device.set_value = AsyncMock(return_value=True)
        # async_set_value() already wrote the optimistic value into the
        # cache before scheduling this background task -- previous_val=0 is
        # only kept around in case the write is never confirmed.
        coordinator = _make_coordinator(
            device=device, cache={"hdwpumpforce": 512}, timestamps={"hdwpumpforce": time.time()}
        )

        await coordinator._perform_repeated_write("hdwpumpforce", 512, previous_val=0)

        assert device.set_value.await_count == 1  # stops at the first real confirmation
        assert coordinator._cache["hdwpumpforce"] == 512  # optimistic value kept
        assert coordinator._timestamps["hdwpumpforce"] == 0  # forces a real re-read next cycle

    @pytest.mark.asyncio
    async def test_never_confirmed_reverts_to_previous_value(self):
        device = MagicMock()
        device.set_value = AsyncMock(return_value=False)
        coordinator = _make_coordinator(device=device, cache={"hdwpumpforce": 512})

        await coordinator._perform_repeated_write("hdwpumpforce", 512, previous_val=0)

        assert device.set_value.await_count == 5  # all attempts exhausted, no early stop
        assert coordinator._cache["hdwpumpforce"] == 0  # reverted, not left at the phantom value
        assert coordinator._timestamps["hdwpumpforce"] == 0

    @pytest.mark.asyncio
    async def test_never_confirmed_with_no_previous_value_clears_cache_entry(self):
        device = MagicMock()
        device.set_value = AsyncMock(return_value=False)
        coordinator = _make_coordinator(device=device, cache={"hdwpumpforce": 512})

        await coordinator._perform_repeated_write("hdwpumpforce", 512, previous_val=None)

        assert "hdwpumpforce" not in coordinator._cache

    @pytest.mark.asyncio
    async def test_async_set_value_is_optimistic_and_schedules_confirmation(self):
        coordinator = _make_coordinator()
        coordinator._perform_repeated_write = AsyncMock()

        result = await coordinator.async_set_value("hdwpumpforce", 512)
        await asyncio.sleep(0)  # let the scheduled background task actually start

        assert result is True
        assert coordinator._cache["hdwpumpforce"] == 512  # painted immediately
        coordinator._perform_repeated_write.assert_called_once_with("hdwpumpforce", 512, None)


class TestBatchedPolling:
    @pytest.mark.asyncio
    async def test_fresh_cache_hits_skip_fetching_entirely(self):
        device = MagicMock()
        device.get_values = AsyncMock(return_value={})
        coordinator = _make_coordinator(
            device=device,
            available_slugs=["tempcwu"],
            cache={"tempcwu": 59.2},
            timestamps={"tempcwu": time.time()},
            ttl=300,
        )

        data = await coordinator._async_update_data()

        device.get_values.assert_not_called()
        assert data["tempcwu"] == 59.2

    @pytest.mark.asyncio
    async def test_stale_slugs_are_fetched_in_one_batched_call(self):
        device = MagicMock()
        device.get_values = AsyncMock(return_value={"a": 10, "b": 20})
        coordinator = _make_coordinator(device=device, available_slugs=["a", "b"])

        data = await coordinator._async_update_data()

        # One call for both slugs -- not one connection per parameter.
        device.get_values.assert_awaited_once_with(["a", "b"], retries=2)
        assert data == {"a": 10, "b": 20}
        assert coordinator._cache == {"a": 10, "b": 20}

    @pytest.mark.asyncio
    async def test_slug_missing_from_batch_result_falls_back_to_cache(self):
        device = MagicMock()
        device.get_values = AsyncMock(return_value={})  # "a" didn't answer this round
        coordinator = _make_coordinator(
            device=device, available_slugs=["a"], cache={"a": 42}, timestamps={"a": 0}
        )

        data = await coordinator._async_update_data()

        assert data["a"] == 42  # held last known state, not dropped

    @pytest.mark.asyncio
    async def test_mixed_fresh_and_stale_only_batches_the_stale_ones(self):
        device = MagicMock()
        device.get_values = AsyncMock(return_value={"stale_slug": 7})
        coordinator = _make_coordinator(
            device=device,
            available_slugs=["fresh_slug", "stale_slug"],
            cache={"fresh_slug": 1, "stale_slug": 0},
            timestamps={"fresh_slug": time.time(), "stale_slug": 0},
        )

        data = await coordinator._async_update_data()

        device.get_values.assert_awaited_once_with(["stale_slug"], retries=2)
        assert data == {"fresh_slug": 1, "stale_slug": 7}


class TestDetectAvailableParametersIncludesSwitchesAndSelects:
    """SWITCH_TYPES/SELECT_TYPES used to be entirely missing from the probe
    target list here, so a switch/select slug was never in available_slugs
    and therefore never re-read by _async_update_data(). Since
    DataUpdateCoordinator.data is fully replaced (not merged) on every
    refresh, that meant a switch's optimistic "on" state reverted to
    unknown at the very next poll cycle regardless of the real hardware
    state -- confirmed against real hardware (IMPROVEMENT_PLAN.md).
    """

    @pytest.mark.asyncio
    async def test_switch_and_select_slugs_are_probed_at_startup(self):
        from custom_components.plum_ecomax.const import SWITCH_TYPES, SELECT_TYPES

        a_switch_slug = next(iter(SWITCH_TYPES))
        a_select_slug = next(iter(SELECT_TYPES))

        device = MagicMock()
        device.params_map = {a_switch_slug: {}, a_select_slug: {}}
        device.get_values = AsyncMock(return_value={a_switch_slug: 1, a_select_slug: 0})
        coordinator = _make_coordinator(device=device)

        await coordinator._detect_available_parameters()

        assert a_switch_slug in coordinator.available_slugs
        assert a_select_slug in coordinator.available_slugs
