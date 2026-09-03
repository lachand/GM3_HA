"""Unit tests for the PlumEconetCalendar entity (comfort-only events)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from custom_components.plum_ecomax.calendar import PlumEconetCalendar
from custom_components.plum_ecomax.const import DOMAIN


def _local(dt):
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.data = {}
    coord.device.params_map = {"circuit1mondayam": {}, "hdwmondayam": {}}
    return coord


@pytest.fixture
def entry():
    e = MagicMock()
    e.entry_id = "test_entry_id"
    return e


def test_unique_ids(coordinator, entry):
    assert (
        PlumEconetCalendar(coordinator, entry, "circuit", 1).unique_id
        == f"{DOMAIN}_test_entry_id_calendar_circuit_1"
    )
    assert (
        PlumEconetCalendar(coordinator, entry, "hdw", 0).unique_id
        == f"{DOMAIN}_test_entry_id_calendar_hdw"
    )


@pytest.mark.asyncio
async def test_only_comfort_blocks_are_emitted(coordinator, entry):
    cal = PlumEconetCalendar(coordinator, entry, "circuit", 1)
    # bits 12..15 set -> comfort 06:00-08:00; eco elsewhere (no event)
    coordinator.data["circuit1mondayam"] = 0b1111_0000_0000_0000
    coordinator.data["circuit1mondaypm"] = 0

    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)  # a Monday
    end = datetime(2024, 1, 1, 23, 59, 59, tzinfo=UTC)
    with patch("custom_components.plum_ecomax.calendar.dt_util.as_local", side_effect=_local):
        events = await cal.async_get_events(MagicMock(), start, end)

    assert len(events) == 1
    assert events[0].summary == "Comfort"
    assert events[0].start == datetime(2024, 1, 1, 6, 0, tzinfo=UTC)
    assert events[0].end == datetime(2024, 1, 1, 8, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_full_am_is_one_block_to_noon(coordinator, entry):
    cal = PlumEconetCalendar(coordinator, entry, "hdw", 0)
    coordinator.data["hdwmondayam"] = 0xFFFFFF
    coordinator.data["hdwmondaypm"] = 0

    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    end = datetime(2024, 1, 1, 23, 59, 59, tzinfo=UTC)
    with patch("custom_components.plum_ecomax.calendar.dt_util.as_local", side_effect=_local):
        events = await cal.async_get_events(MagicMock(), start, end)

    assert len(events) == 1
    assert events[0].start == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert events[0].end == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_no_events_when_register_data_missing(coordinator, entry):
    cal = PlumEconetCalendar(coordinator, entry, "circuit", 1)
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    end = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    with patch("custom_components.plum_ecomax.calendar.dt_util.as_local", side_effect=_local):
        assert await cal.async_get_events(MagicMock(), start, end) == []
