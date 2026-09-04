"""Unit tests for the automatic solar-dump dT controller in solar_dump.py.

The controller ticks every AUTO_TICK_SECONDS while switch.solar_dump_auto is
on: run the transfer pump in bursts when DHW is hotter than the buffer by
>= dt_start, stop below AUTO_DT_STOP; charge hard until the buffer target,
then only skim gradients >= 2*dt_start; never drain DHW below the auto
floor; respect a daily circulator budget and anti-short-cycle timers.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.plum_ecomax import solar_dump
from custom_components.plum_ecomax.const import AUTO_MIN_REST_SECONDS, AUTO_MIN_RUN_SECONDS
from custom_components.plum_ecomax.solar_dump import _AUTO, _OWNER, _RUNNING, _auto_tick


class Clock:
    def __init__(self, mono=10_000.0, wall=datetime(2026, 6, 15, 12, 0, 0)):
        self.mono = mono
        self.wall = wall

    def advance(self, seconds):
        self.mono += seconds
        self.wall = self.wall.fromtimestamp(self.wall.timestamp() + seconds)


def _coord(ecs=60.0, buffer=40.0, *, target=55, floor=45, dt_start=8, budget=120, legion_hour=None):
    c = MagicMock()
    c.data = {"tempcwu": ecs, "tempbufordown": buffer, "hdwlegionhour": legion_hour}
    c.solar_dump_auto_ecs_floor = floor
    c.solar_dump_buffer_target = target
    c.solar_dump_dt_start = dt_start
    c.solar_dump_daily_budget = budget
    return c


@pytest.fixture
def env():
    clk = Clock()
    _AUTO.clear()
    _OWNER.clear()
    _RUNNING.clear()
    start = AsyncMock()
    stop = AsyncMock()

    async def _fake_start(hass, coordinator, entry_id, **kw):
        _OWNER[entry_id] = "auto"
        t = MagicMock()
        t.done.return_value = False
        _RUNNING[entry_id] = t

    async def _fake_stop(hass, entry_id):
        _OWNER.pop(entry_id, None)
        _RUNNING.pop(entry_id, None)

    start.side_effect = _fake_start
    stop.side_effect = _fake_stop
    with (
        patch.object(solar_dump, "async_start_hold", start),
        patch.object(solar_dump, "async_stop_for_entry", stop),
        patch.object(solar_dump.time, "monotonic", lambda: clk.mono),
        patch.object(solar_dump.dt_util, "now", lambda: clk.wall),
    ):
        yield clk, start, stop
    _AUTO.clear()
    _OWNER.clear()
    _RUNNING.clear()


async def _tick(coord):
    await _auto_tick(MagicMock(), coord, "e1")


def _running():
    return _OWNER.get("e1") == "auto" and "e1" in _RUNNING


@pytest.mark.asyncio
async def test_charge_mode_starts_a_burst(env):
    _clk, start, _stop = env
    await _tick(_coord(ecs=60, buffer=40, target=55))  # dt=20 >= 8, buffer < target
    start.assert_awaited_once()
    assert start.await_args.kwargs["owner"] == "auto"
    assert _running()


@pytest.mark.asyncio
async def test_no_burst_when_gradient_too_small(env):
    _clk, start, _stop = env
    await _tick(_coord(ecs=45, buffer=41))  # dt=4 < 8
    start.assert_not_awaited()


@pytest.mark.asyncio
async def test_balance_mode_needs_double_the_gradient(env):
    _clk, start, _stop = env
    # buffer at/above target -> needs dt >= 2*dt_start (16)
    await _tick(_coord(ecs=68, buffer=56, target=55, dt_start=8))  # dt=12 < 16
    start.assert_not_awaited()
    await _tick(_coord(ecs=73, buffer=56, target=55, dt_start=8))  # dt=17 >= 16
    start.assert_awaited_once()


@pytest.mark.asyncio
async def test_floor_stops_a_running_burst_immediately(env):
    clk, _start, stop = env
    await _tick(_coord(ecs=60, buffer=40))
    assert _running()
    clk.advance(60)  # less than MIN_RUN
    await _tick(_coord(ecs=44, buffer=40, floor=45))  # ecs <= floor -> hard OFF
    stop.assert_awaited_once()
    assert not _running()


@pytest.mark.asyncio
async def test_min_run_blocks_an_early_normal_stop(env):
    clk, _start, stop = env
    await _tick(_coord(ecs=60, buffer=40))
    clk.advance(60)  # << AUTO_MIN_RUN_SECONDS
    await _tick(_coord(ecs=50, buffer=49))  # dt=1 < AUTO_DT_STOP but not a hard-OFF
    stop.assert_not_awaited()
    clk.advance(AUTO_MIN_RUN_SECONDS)
    await _tick(_coord(ecs=50, buffer=49))
    stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_min_rest_blocks_an_immediate_restart(env):
    clk, start, stop = env
    await _tick(_coord(ecs=60, buffer=40))
    clk.advance(AUTO_MIN_RUN_SECONDS + 1)
    await _tick(_coord(ecs=48, buffer=49))  # stop (dt negative)
    assert stop.await_count == 1
    start.reset_mock()
    clk.advance(60)  # << AUTO_MIN_REST_SECONDS
    await _tick(_coord(ecs=62, buffer=40))  # big gradient again
    start.assert_not_awaited()
    clk.advance(AUTO_MIN_REST_SECONDS)
    await _tick(_coord(ecs=62, buffer=40))
    start.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_budget_caps_bursts(env):
    _clk, start, _stop = env
    _AUTO["e1"] = solar_dump._fresh_auto_state()
    _AUTO["e1"]["runtime_today"] = 130  # over the 120 default
    await _tick(_coord(ecs=70, buffer=40, budget=120))
    start.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_is_a_noop_when_someone_else_owns_the_session(env):
    _clk, start, stop = env
    _OWNER["e1"] = "manual"
    _RUNNING["e1"] = MagicMock()
    await _tick(_coord(ecs=70, buffer=40))
    start.assert_not_awaited()
    stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_anti_legionella_hour_is_skipped(env):
    clk, start, _stop = env
    await _tick(_coord(ecs=70, buffer=40, legion_hour=clk.wall.hour))
    start.assert_not_awaited()


@pytest.mark.asyncio
async def test_bad_sensor_reads_skip_the_tick(env):
    _clk, start, _stop = env
    c = _coord()
    c.data["tempcwu"] = None
    await _tick(c)
    start.assert_not_awaited()
    c.data["tempcwu"] = 60
    c.data["tempbufordown"] = 999  # fault
    await _tick(c)
    start.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_accumulates_across_a_burst(env):
    clk, _start, _stop = env
    await _tick(_coord(ecs=60, buffer=40))
    clk.advance(600)  # 10 min
    await _tick(_coord(ecs=48, buffer=49))  # normal stop (MIN_RUN satisfied)
    assert 9.5 <= _AUTO["e1"]["runtime_today"] <= 10.5
    assert 9.5 <= solar_dump.auto_runtime_minutes("e1") <= 10.5


@pytest.mark.asyncio
async def test_midnight_rollover_resets_runtime(env):
    clk, _s, _st = env
    _AUTO["e1"] = solar_dump._fresh_auto_state()
    _AUTO["e1"]["runtime_today"] = 90
    _AUTO["e1"]["day"] = clk.wall.date()
    clk.advance(86400)  # next day
    await _tick(_coord(ecs=45, buffer=44))  # any tick
    assert _AUTO["e1"]["runtime_today"] == 0.0
