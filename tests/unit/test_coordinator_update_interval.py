"""Unit test for PlumDataUpdateCoordinator's configurable polling interval
(CONF_UPDATE_INTERVAL in const.py -- lets a per-install polling interval be
set via the config/options flow instead of the hardcoded 30s default).

DataUpdateCoordinator.__init__ itself is patched out rather than called for
real: it does frame-helper / debouncer setup that needs a fuller hass than
this project's hass=MagicMock() fixture. Patching it lets this test observe
exactly what PlumDataUpdateCoordinator forwards upstream.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.plum_ecomax.const import UPDATE_INTERVAL
from custom_components.plum_ecomax.coordinator import PlumDataUpdateCoordinator


def _entry(entry_id="entry123"):
    entry = MagicMock()
    entry.entry_id = entry_id
    return entry


def _captured_base_init():
    captured = {}

    def fake_init(self, hass, logger, *, name, config_entry=None, update_interval=None, **kwargs):
        captured["update_interval"] = update_interval
        captured["config_entry"] = config_entry

    return captured, fake_init


def test_custom_update_interval_is_passed_upstream_as_timedelta():
    captured, fake_init = _captured_base_init()

    with patch.object(DataUpdateCoordinator, "__init__", fake_init):
        PlumDataUpdateCoordinator(MagicMock(), MagicMock(), _entry(), update_interval=90)

    assert captured["update_interval"] == timedelta(seconds=90)


def test_default_update_interval_used_when_not_specified():
    captured, fake_init = _captured_base_init()

    with patch.object(DataUpdateCoordinator, "__init__", fake_init):
        PlumDataUpdateCoordinator(MagicMock(), MagicMock(), _entry())

    assert captured["update_interval"] == timedelta(seconds=UPDATE_INTERVAL)


def test_config_entry_is_passed_upstream_and_entry_id_stored_for_issue_scoping():
    captured, fake_init = _captured_base_init()
    entry = _entry("entry123")

    with patch.object(DataUpdateCoordinator, "__init__", fake_init):
        coordinator = PlumDataUpdateCoordinator(MagicMock(), MagicMock(), entry)

    assert captured["config_entry"] is entry
    assert coordinator.entry_id == "entry123"
