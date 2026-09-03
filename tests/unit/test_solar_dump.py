"""Unit tests for solar_dump.py -- the plum_ecomax.solar_to_buffer service.

The service replays the ecoSTER "manual control" screen's two writes
(operating mode 161 = 2, hdwpumpforce 172 = 512), holds them for a capped
duration, and must ALWAYS return the boiler to automatic afterwards -- on
the timer, on a replacing call, and on async_stop_for_entry (unload/stop).
Manual mode disables automatic regulation, so the guaranteed restore is the
part that matters most.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.plum_ecomax import solar_dump
from custom_components.plum_ecomax.const import (
    DOMAIN,
    MANUAL_MODE_BIT,
    OPERATING_MODE_AUTO,
    OPERATING_MODE_MANUAL,
)
from custom_components.plum_ecomax.solar_dump import (
    _RUNNING,
    _handle_solar_to_buffer,
    async_stop_for_entry,
)

# Captured before any test patches asyncio.sleep -- test helpers use this to
# yield to the loop regardless of what the code-under-test's sleep is mocked to.
_REAL_SLEEP = asyncio.sleep


class FakeDevice:
    """Records set_value calls; get_value answers from a scripted state."""

    def __init__(self, start_mode=OPERATING_MODE_AUTO, manual_bit_follows=True):
        self.writes: list[tuple[str, int]] = []
        self._mode = start_mode
        self._force = 0
        self._manual_bit_follows = manual_bit_follows
        self.set_value = AsyncMock(side_effect=self._set)
        self.get_value = AsyncMock(side_effect=self._get)

    async def _set(self, slug, value, **_):
        self.writes.append((slug, value))
        if slug == "operatingmode":
            self._mode = value
        elif slug == "hdwpumpforce":
            self._force = value
        return True

    async def _get(self, slug, **_):
        if slug == "operatingmode":
            return self._mode
        if slug == "heatsourcemainpumpstate":
            manual = self._mode == OPERATING_MODE_MANUAL and self._manual_bit_follows
            return MANUAL_MODE_BIT if manual else 0
        if slug == "hdwpumpforce":
            return self._force
        return None


def _make_hass():
    hass = MagicMock()
    hass.async_create_task = lambda coro, name=None: asyncio.ensure_future(coro)
    return hass


def _make_call(duration):
    call = MagicMock()
    call.data = {"duration": duration}
    return call


@pytest.fixture(autouse=True)
def _clear_running():
    _RUNNING.clear()
    yield
    _RUNNING.clear()


@pytest.fixture(autouse=True)
def _instant_sleep():
    async def _noop(_seconds):
        return None

    with patch.object(solar_dump.asyncio, "sleep", _noop):
        yield


@pytest.fixture(autouse=True)
def _mock_issues():
    with (
        patch.object(solar_dump, "raise_issue") as raise_mock,
        patch.object(solar_dump, "clear_issue") as clear_mock,
    ):
        yield raise_mock, clear_mock


async def _run_service(hass, call):
    await _handle_solar_to_buffer(hass, call)
    tasks = list(_RUNNING.values())
    for task in tasks:
        await task


async def _wait_until(predicate, turns=500):
    for _ in range(turns):
        if predicate():
            return
        await _REAL_SLEEP(0)
    raise AssertionError("condition not reached")


@pytest.mark.asyncio
async def test_no_coordinators_is_a_noop(caplog):
    hass = _make_hass()
    hass.data = {DOMAIN: {}}
    await _handle_solar_to_buffer(hass, _make_call(30))
    assert not _RUNNING


@pytest.mark.asyncio
async def test_happy_path_writes_then_restores():
    dev = FakeDevice()
    hass = _make_hass()
    hass.data = {DOMAIN: {"e1": MagicMock(device=dev)}}

    await _run_service(hass, _make_call(30))

    assert dev.writes == [
        ("operatingmode", OPERATING_MODE_MANUAL),
        ("hdwpumpforce", 512),
        ("hdwpumpforce", 0),
        ("operatingmode", OPERATING_MODE_AUTO),
    ]
    assert not _RUNNING


@pytest.mark.asyncio
async def test_duration_is_capped_at_120_minutes():
    dev = FakeDevice()
    hass = _make_hass()
    hass.data = {DOMAIN: {"e1": MagicMock(device=dev)}}

    seen: list[float] = []

    async def _record(seconds):
        seen.append(seconds)

    with patch.object(solar_dump.asyncio, "sleep", _record):
        await _run_service(hass, _make_call(9999))

    # The long hold sleep is the largest; it must be 120 min, not 9999.
    assert max(seen) == 120 * 60


@pytest.mark.asyncio
async def test_aborts_without_writing_if_not_in_automatic():
    dev = FakeDevice(start_mode=OPERATING_MODE_MANUAL)
    hass = _make_hass()
    hass.data = {DOMAIN: {"e1": MagicMock(device=dev)}}

    await _run_service(hass, _make_call(30))

    assert dev.writes == []


@pytest.mark.asyncio
async def test_restores_even_if_manual_mode_not_confirmed_by_telemetry():
    dev = FakeDevice(manual_bit_follows=False)  # bit 64 never appears
    hass = _make_hass()
    hass.data = {DOMAIN: {"e1": MagicMock(device=dev)}}

    await _run_service(hass, _make_call(30))

    # Entered manual, never forced the pump, but still wrote it back to auto.
    assert ("operatingmode", OPERATING_MODE_MANUAL) in dev.writes
    assert ("hdwpumpforce", 512) not in dev.writes
    assert dev.writes[-1] == ("operatingmode", OPERATING_MODE_AUTO)


@pytest.mark.asyncio
async def test_stop_for_entry_cancels_and_restores():
    dev = FakeDevice()
    hass = _make_hass()
    hass.data = {DOMAIN: {"e1": MagicMock(device=dev)}}

    # A hold that would otherwise block forever.
    async def _forever(seconds):
        if seconds >= 60:
            await asyncio.Event().wait()

    with patch.object(solar_dump.asyncio, "sleep", _forever):
        await _handle_solar_to_buffer(hass, _make_call(30))
        await _wait_until(lambda: ("hdwpumpforce", 512) in dev.writes)
        await async_stop_for_entry(hass, "e1")

    assert dev.writes[-2:] == [("hdwpumpforce", 0), ("operatingmode", OPERATING_MODE_AUTO)]
    assert not _RUNNING


@pytest.mark.asyncio
async def test_second_call_restarts_the_run():
    dev = FakeDevice()
    hass = _make_hass()
    hass.data = {DOMAIN: {"e1": MagicMock(device=dev)}}

    async def _forever(seconds):
        if seconds >= 60:
            await asyncio.Event().wait()

    with patch.object(solar_dump.asyncio, "sleep", _forever):
        await _handle_solar_to_buffer(hass, _make_call(30))
        await _wait_until(lambda: ("hdwpumpforce", 512) in dev.writes)
        first = next(iter(_RUNNING.values()))

        await _handle_solar_to_buffer(hass, _make_call(30))
        await _wait_until(lambda: dev.writes.count(("hdwpumpforce", 512)) == 2)
        second = next(iter(_RUNNING.values()))
        assert first is not second

        await async_stop_for_entry(hass, "e1")

    # restore ran for the cancelled first run and again for the stopped second
    assert dev.writes.count(("operatingmode", OPERATING_MODE_AUTO)) >= 2


@pytest.mark.asyncio
async def test_restore_failure_raises_issue(_mock_issues):
    raise_mock, _clear_mock = _mock_issues
    dev = FakeDevice()

    async def _set_fail_on_restore(slug, value, **_):
        dev.writes.append((slug, value))
        if slug == "operatingmode" and value == OPERATING_MODE_MANUAL:
            dev._mode = value
            return True
        # the forward pump-force write succeeds; every restore write fails
        return slug == "hdwpumpforce" and value == 512

    dev.set_value = AsyncMock(side_effect=_set_fail_on_restore)
    hass = _make_hass()
    hass.data = {DOMAIN: {"e1": MagicMock(device=dev)}}

    await _run_service(hass, _make_call(5))

    assert raise_mock.called
    assert raise_mock.call_args[0][1] == solar_dump.STUCK_ISSUE_ID
