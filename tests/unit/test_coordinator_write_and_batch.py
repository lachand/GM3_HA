"""Unit tests for coordinator.py: write-failure propagation and batched
polling (Family: coordinator, mocked device).

Builds PlumDataUpdateCoordinator via `object.__new__` instead of calling
its real `__init__`: `DataUpdateCoordinator.__init__` on the `homeassistant`
version this suite currently resolves calls `frame.report_usage`, which
raises `RuntimeError: Frame helper not set up` against this project's
lightweight `hass=MagicMock()` fixture (pre-existing gap, unrelated to
this diff -- see IMPROVEMENT_PLAN.md). Only the attributes
`_async_update_data`/`async_set_value`/`_perform_repeated_write` actually
touch are seeded: `device`, `hass`, `entry_id`, `available_slugs`,
`_cache`, `_timestamps`, `_cache_lock`, `ttl`. `async_set_updated_data` is
stubbed out since it belongs to the DataUpdateCoordinator base and isn't
part of what's tested here. `raise_issue`/`clear_issue` are patched to
plain Mocks for every test in this file (autouse) since most of these
tests don't care about repair-issue side effects -- tests that DO care
request the `_mock_issues` fixture by name to get the same Mocks and
assert on them.
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


@pytest.fixture(autouse=True)
def _mock_issues(monkeypatch):
    mock_raise = MagicMock()
    mock_clear = MagicMock()
    monkeypatch.setattr("custom_components.plum_ecomax.coordinator.raise_issue", mock_raise)
    monkeypatch.setattr("custom_components.plum_ecomax.coordinator.clear_issue", mock_clear)
    return mock_raise, mock_clear


def _make_coordinator(device=None, available_slugs=None, cache=None, timestamps=None, ttl=300, entry_id="entry123"):
    coordinator = object.__new__(PlumDataUpdateCoordinator)
    coordinator.device = device if device is not None else MagicMock()
    # _validate_value() does `self.device.params_map.get(slug, {})`; on a
    # bare MagicMock, .params_map and its .get() are themselves mocks, not
    # a real dict, which breaks the JSON-bounds comparisons downstream.
    if not isinstance(coordinator.device.params_map, dict):
        coordinator.device.params_map = {}
    # consecutive_failures/last_write_error are read unconditionally by
    # _update_connection_issue()/_perform_repeated_write() -- a bare
    # MagicMock().device would make these themselves Mocks, breaking the
    # int comparison / hex-formatting that reads them.
    if not isinstance(coordinator.device.consecutive_failures, int):
        coordinator.device.consecutive_failures = 0
    if isinstance(coordinator.device.last_write_error, MagicMock):
        coordinator.device.last_write_error = None
    coordinator.hass = MagicMock()
    coordinator.entry_id = entry_id
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


class TestWriteRejectedIssue:
    """coordinator.py section K/L: a write the boiler explicitly rejects
    (e.g. 0x7D auth error) raises a "write_rejected" repair issue, distinct
    from a write that just never got any response at all (still only the
    pre-existing warning log, nothing new to tell the user).
    """

    @pytest.mark.asyncio
    async def test_confirmed_write_clears_any_open_rejection_issue(self, _mock_issues):
        mock_raise, mock_clear = _mock_issues
        device = MagicMock()
        device.set_value = AsyncMock(return_value=True)
        coordinator = _make_coordinator(device=device, cache={"hdwpumpforce": 512}, entry_id="entryA")

        await coordinator._perform_repeated_write("hdwpumpforce", 512, previous_val=0)

        mock_clear.assert_called_once_with(coordinator.hass, "write_rejected_entryA_hdwpumpforce")
        mock_raise.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_rejection_raises_issue_with_the_code(self, _mock_issues):
        mock_raise, mock_clear = _mock_issues
        device = MagicMock()
        device.set_value = AsyncMock(return_value=False)
        device.last_write_error = 0x7D
        coordinator = _make_coordinator(device=device, cache={"hdwpumpforce": 512}, entry_id="entryA")

        await coordinator._perform_repeated_write("hdwpumpforce", 512, previous_val=0)

        mock_raise.assert_called_once()
        args, kwargs = mock_raise.call_args
        assert args[0] is coordinator.hass
        assert args[1] == "write_rejected_entryA_hdwpumpforce"
        assert args[2] == "write_rejected"
        assert kwargs["translation_placeholders"] == {"slug": "hdwpumpforce", "code": "0x7D"}
        mock_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_never_answered_at_all_does_not_raise_an_issue(self, _mock_issues):
        """Distinct from an explicit rejection: no response ever arrived,
        so there's no specific code to report -- the existing warning log
        already covers this, connection_lost covers persistent
        unreachability. Not raising here avoids a issue that says nothing
        actionable beyond what those two already provide.
        """
        mock_raise, mock_clear = _mock_issues
        device = MagicMock()
        device.set_value = AsyncMock(return_value=False)
        device.last_write_error = None
        coordinator = _make_coordinator(device=device, cache={"hdwpumpforce": 512}, entry_id="entryA")

        await coordinator._perform_repeated_write("hdwpumpforce", 512, previous_val=0)

        mock_raise.assert_not_called()
        mock_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_issue_id_is_scoped_by_entry_and_slug(self, _mock_issues):
        mock_raise, _ = _mock_issues
        device = MagicMock()
        device.set_value = AsyncMock(return_value=False)
        device.last_write_error = 0x7F
        coordinator = _make_coordinator(device=device, cache={"otherslug": 1}, entry_id="entryB")

        await coordinator._perform_repeated_write("otherslug", 1, previous_val=0)

        assert mock_raise.call_args.args[1] == "write_rejected_entryB_otherslug"


class TestConnectionLostIssue:
    """coordinator.py: PlumDevice.consecutive_failures crossing
    CONNECTION_LOST_THRESHOLD raises a "connection_lost" repair issue;
    dropping back below it clears the issue. Checked unconditionally every
    _async_update_data() cycle, independent of whether that cycle actually
    attempted a transaction (see CONNECTION_LOST_THRESHOLD's comment in
    coordinator.py for why).
    """

    @pytest.mark.asyncio
    async def test_below_threshold_clears_issue(self, _mock_issues):
        mock_raise, mock_clear = _mock_issues
        device = MagicMock()
        device.consecutive_failures = 2
        device.get_values = AsyncMock(return_value={})
        coordinator = _make_coordinator(device=device, available_slugs=["dummy"], entry_id="entryA")

        await coordinator._async_update_data()

        mock_clear.assert_called_once_with(coordinator.hass, "connection_lost_entryA")
        mock_raise.assert_not_called()

    @pytest.mark.asyncio
    async def test_at_threshold_raises_issue_with_count(self, _mock_issues):
        mock_raise, mock_clear = _mock_issues
        device = MagicMock()
        device.consecutive_failures = 3
        device.get_values = AsyncMock(return_value={})
        coordinator = _make_coordinator(device=device, available_slugs=["dummy"], entry_id="entryA")

        await coordinator._async_update_data()

        mock_raise.assert_called_once()
        args, kwargs = mock_raise.call_args
        assert args[0] is coordinator.hass
        assert args[1] == "connection_lost_entryA"
        assert args[2] == "connection_lost"
        assert kwargs["translation_placeholders"] == {"count": "3"}
        mock_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_issue_id_is_scoped_by_entry(self, _mock_issues):
        mock_raise, _ = _mock_issues
        device = MagicMock()
        device.consecutive_failures = 5
        device.get_values = AsyncMock(return_value={})
        coordinator = _make_coordinator(device=device, available_slugs=["dummy"], entry_id="entryB")

        await coordinator._async_update_data()

        assert mock_raise.call_args.args[1] == "connection_lost_entryB"


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
