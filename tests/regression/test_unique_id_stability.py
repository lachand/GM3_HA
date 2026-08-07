"""Regression test: unique_id snapshot for every platform's entity class.

`unique_id` is what Home Assistant uses to track "is this the same entity
as before" across restarts -- silently changing its format orphans every
existing user's entity (history, automations, dashboard cards all
reference the old one) and creates a duplicate. This pins the current
format for every platform so that changing it is a deliberate, visible
diff instead of an incidental one.

Entities are instantiated directly (not through async_setup_entry/hass)
since their __init__ only needs a coordinator and a few plain arguments --
see tests/unit/test_plum_device.py's docstring for why the heavier
DataUpdateCoordinator/ConfigEntry test harness is avoided here too.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.plum_ecomax.calendar import PlumEconetCalendar
from custom_components.plum_ecomax.climate import PlumEcomaxClimate
from custom_components.plum_ecomax.number import PlumEcomaxNumber
from custom_components.plum_ecomax.select import PlumEconetSelect
from custom_components.plum_ecomax.sensor import PlumEcomaxSensor
from custom_components.plum_ecomax.switch import PlumEconetSwitch
from custom_components.plum_ecomax.water_heater import PlumEcomaxWaterHeater

ENTRY_ID = "entry123"
_ENTRY = SimpleNamespace(entry_id=ENTRY_ID)


def _coordinator():
    return MagicMock()


class TestUniqueIdSnapshot:
    def test_switch(self):
        entity = PlumEconetSwitch(_coordinator(), ENTRY_ID, "hdwpumpforce", "Force pump", 512, 0)
        assert entity.unique_id == f"plum_ecomax_{ENTRY_ID}_switch_hdwpumpforce"

    def test_select(self):
        entity = PlumEconetSelect(_coordinator(), ENTRY_ID, "hdwusermode", "DHW Mode", {0: "off"}, {"off": 0})
        assert entity.unique_id == f"plum_ecomax_{ENTRY_ID}_select_hdwusermode"

    def test_number(self):
        entity = PlumEcomaxNumber(_coordinator(), _ENTRY, "hdwtsetpoint", (10, 60, 1, "mdi:thermometer"))
        assert entity.unique_id == f"plum_ecomax_{ENTRY_ID}_number_hdwtsetpoint"

    def test_water_heater(self):
        entity = PlumEcomaxWaterHeater(_coordinator(), ENTRY_ID, "hdw", "cur", "tgt", "min", "max", "mode")
        assert entity.unique_id == f"plum_ecomax_{ENTRY_ID}_hdw"

    def test_sensor(self):
        entity = PlumEcomaxSensor(_coordinator(), _ENTRY, "tempcwu", ("°C", "mdi:thermometer", "temperature"))
        assert entity.unique_id == f"plum_ecomax_{ENTRY_ID}_tempcwu"

    def test_climate(self):
        entity = PlumEcomaxClimate(_coordinator(), _ENTRY, 2, "cur_slug", "tgt_slug", "active_slug")
        assert entity.unique_id == f"plum_ecomax_{ENTRY_ID}_circuit_2_climate"

    def test_calendar_circuit(self):
        entity = PlumEconetCalendar(_coordinator(), _ENTRY, "circuit", 2)
        assert entity.unique_id == f"plum_ecomax_{ENTRY_ID}_calendar_circuit_2"

    def test_calendar_hdw(self):
        entity = PlumEconetCalendar(_coordinator(), _ENTRY, "hdw", 0)
        assert entity.unique_id == f"plum_ecomax_{ENTRY_ID}_calendar_hdw"
