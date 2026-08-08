"""Unit test for PlumDataUpdateCoordinator's configurable polling interval
(CONF_UPDATE_INTERVAL in const.py -- lets a per-install polling interval be
set via the config/options flow instead of the hardcoded 30s default).

DataUpdateCoordinator.__init__ itself is patched out rather than called for
real: on the installed homeassistant release it calls
frame.report_usage(), which raises against this project's lightweight
hass=MagicMock() (see the same note in tests/test_coordinator.py). Patching
it lets this test observe exactly what PlumDataUpdateCoordinator passes
upstream without needing a full hass/frame-helper setup.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.plum_ecomax.const import UPDATE_INTERVAL
from custom_components.plum_ecomax.coordinator import PlumDataUpdateCoordinator


def _captured_base_init():
    captured = {}

    def fake_init(self, hass, logger, *, name, update_interval=None, **kwargs):
        captured["update_interval"] = update_interval

    return captured, fake_init


def test_custom_update_interval_is_passed_upstream_as_timedelta():
    captured, fake_init = _captured_base_init()

    with patch.object(DataUpdateCoordinator, "__init__", fake_init):
        PlumDataUpdateCoordinator(MagicMock(), MagicMock(), "entry123", update_interval=90)

    assert captured["update_interval"] == timedelta(seconds=90)


def test_default_update_interval_used_when_not_specified():
    captured, fake_init = _captured_base_init()

    with patch.object(DataUpdateCoordinator, "__init__", fake_init):
        PlumDataUpdateCoordinator(MagicMock(), MagicMock(), "entry123")

    assert captured["update_interval"] == timedelta(seconds=UPDATE_INTERVAL)


def test_entry_id_is_stored_for_issue_id_scoping():
    _, fake_init = _captured_base_init()

    with patch.object(DataUpdateCoordinator, "__init__", fake_init):
        coordinator = PlumDataUpdateCoordinator(MagicMock(), MagicMock(), "entry123")

    assert coordinator.entry_id == "entry123"
