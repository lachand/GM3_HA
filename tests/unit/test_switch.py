"""Unit tests for switch.py.

Covers async_setup_entry filtering (only creates entities for slugs present
in the device map), on/off state derivation from arbitrary on_value/
off_value pairs (not just 1/0 -- e.g. hdwpumpforce uses 512/0), the write
path, and device routing (HDW_SWITCHES -> DHW device, everything else ->
boiler device), plus unique_id scoping by entry_id -- the pattern that was
missing here before device.py existed (IMPROVEMENT_PLAN.md section C).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.plum_ecomax.const import DOMAIN, SWITCH_TYPES
from custom_components.plum_ecomax.switch import HDW_SWITCHES, PlumEconetSwitch, async_setup_entry


def _make_coordinator(params_map: dict, data: dict):
    coordinator = MagicMock()
    coordinator.device.params_map = params_map
    coordinator.data = data
    coordinator.async_set_value = AsyncMock(return_value=True)
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry_only_creates_entities_present_in_device_map():
    coordinator = _make_coordinator({"hdwpumpforce": {"id": 172}}, {})
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry123"
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    slugs = {e._slug for e in added}
    assert slugs == {"hdwpumpforce"}


@pytest.mark.asyncio
async def test_async_setup_entry_skips_slugs_not_in_device_map():
    coordinator = _make_coordinator({}, {})
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry123"
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    assert added == []


class TestIsOn:
    def test_is_on_true_for_nonstandard_on_value(self):
        # hdwpumpforce's "on" is 512, not 1 -- a naive bool(int(val)) check
        # would also report on for e.g. 2, so this pins the exact-match
        # comparison against on_value.
        name, on_value, off_value = SWITCH_TYPES["hdwpumpforce"]
        coordinator = _make_coordinator({}, {"hdwpumpforce": 512})
        switch = PlumEconetSwitch(coordinator, "entry123", "hdwpumpforce", name, on_value, off_value)

        assert switch.is_on is True

    def test_is_on_false_for_off_value(self):
        name, on_value, off_value = SWITCH_TYPES["hdwpumpforce"]
        coordinator = _make_coordinator({}, {"hdwpumpforce": 0})
        switch = PlumEconetSwitch(coordinator, "entry123", "hdwpumpforce", name, on_value, off_value)

        assert switch.is_on is False

    def test_is_on_false_when_value_missing(self):
        name, on_value, off_value = SWITCH_TYPES["hdwpumpforce"]
        coordinator = _make_coordinator({}, {})
        switch = PlumEconetSwitch(coordinator, "entry123", "hdwpumpforce", name, on_value, off_value)

        assert switch.is_on is False

    def test_is_on_false_for_non_numeric_value(self):
        name, on_value, off_value = SWITCH_TYPES["hdwpumpforce"]
        coordinator = _make_coordinator({}, {"hdwpumpforce": "not-a-number"})
        switch = PlumEconetSwitch(coordinator, "entry123", "hdwpumpforce", name, on_value, off_value)

        assert switch.is_on is False


class TestWritePath:
    @pytest.mark.asyncio
    async def test_turn_on_writes_on_value(self):
        name, on_value, off_value = SWITCH_TYPES["hdwpumpforce"]
        coordinator = _make_coordinator({}, {})
        switch = PlumEconetSwitch(coordinator, "entry123", "hdwpumpforce", name, on_value, off_value)

        await switch.async_turn_on()

        coordinator.async_set_value.assert_awaited_once_with("hdwpumpforce", 512)

    @pytest.mark.asyncio
    async def test_turn_off_writes_off_value(self):
        name, on_value, off_value = SWITCH_TYPES["hdwpumpforce"]
        coordinator = _make_coordinator({}, {})
        switch = PlumEconetSwitch(coordinator, "entry123", "hdwpumpforce", name, on_value, off_value)

        await switch.async_turn_off()

        coordinator.async_set_value.assert_awaited_once_with("hdwpumpforce", 0)


class TestDeviceRouting:
    def test_hdw_switches_route_to_dhw_device(self):
        coordinator = _make_coordinator({}, {})
        for slug in HDW_SWITCHES:
            name, on_value, off_value = SWITCH_TYPES[slug]
            switch = PlumEconetSwitch(coordinator, "entry123", slug, name, on_value, off_value)
            info = switch.device_info
            assert (DOMAIN, "entry123_hdw") in info["identifiers"]

    def test_non_hdw_switch_routes_to_boiler_device(self):
        coordinator = _make_coordinator({}, {"uid": "SN123"})
        switch = PlumEconetSwitch(coordinator, "entry123", "some_other_slug", "Other", 1, 0)

        info = switch.device_info

        assert (DOMAIN, "entry123") in info["identifiers"]
        assert info["serial_number"] == "SN123"


def test_unique_id_is_scoped_by_entry_id():
    coordinator = _make_coordinator({}, {})
    name, on_value, off_value = SWITCH_TYPES["hdwpumpforce"]
    switch_a = PlumEconetSwitch(coordinator, "entryA", "hdwpumpforce", name, on_value, off_value)
    switch_b = PlumEconetSwitch(coordinator, "entryB", "hdwpumpforce", name, on_value, off_value)

    assert switch_a.unique_id != switch_b.unique_id
    assert "entryA" in switch_a.unique_id
    assert "entryB" in switch_b.unique_id
