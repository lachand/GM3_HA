"""Diagnostics support for the Plum EcoMAX integration.

Lets a user download a redacted snapshot (config entry data with
credentials stripped, coordinator cache, detected parameters) straight
from the Home Assistant UI (Settings > Devices & Services > Plum EcoMAX >
Download diagnostics) instead of having to reproduce state by hand for a
bug report.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "device": {
            "ip": device.ip,
            "port": device.port,
            "map_file": device.map_file,
            "params_map_size": len(device.params_map),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception) if coordinator.last_exception else None,
            "available_slugs": sorted(coordinator.available_slugs),
            "cached_data": dict(coordinator.data) if coordinator.data else {},
        },
    }
