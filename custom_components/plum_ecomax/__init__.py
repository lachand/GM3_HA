"""The main entry point for the Plum EcoMAX integration.

This module handles the setup, configuration, and unloading of the
integration through Home Assistant's Config Flow.
"""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import CONF_UPDATE_INTERVAL, DEFAULT_PORT, DOMAIN, UPDATE_INTERVAL
from .coordinator import PlumDataUpdateCoordinator
from .plum_device import PlumDevice

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [
    "climate",
    "sensor",
    "number",
    "switch",
    "select",
    "water_heater",
    "calendar",
    "button",
    "binary_sensor",
]

# This integration is only ever set up from a config entry (Settings ->
# Devices & Services -> Add Integration), never from configuration.yaml --
# tells hassfest/HA there's deliberately no YAML schema to validate.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Plum EcoMAX component.

    Args:
        hass: The Home Assistant instance.
        config: The configuration dictionary.

    Returns:
        bool: Always True (configuration is handled via Config Flow).
    """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Plum EcoMAX from a config entry.

    This function initializes the connection to the boiler, loads the
    device parameter map, creates the data coordinator, and sets up
    the various platforms (sensor, climate, etc.).

    Args:
        hass: The Home Assistant instance.
        entry: The config entry containing connection details.

    Returns:
        bool: True if setup was successful.
    """
    ip = entry.data.get(CONF_IP_ADDRESS)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    password = entry.data.get(CONF_PASSWORD, "0000")

    filename = "device_map_ecomax360i.json"
    json_path = hass.config.path(f"custom_components/{DOMAIN}/{filename}")

    device = PlumDevice(ip, port=port, password=password, map_file=json_path)

    try:
        await asyncio.to_thread(device.load_map)
    except Exception as err:
        raise ConfigEntryNotReady(f"Could not load parameter map {json_path}: {err}") from err

    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)
    coordinator = PlumDataUpdateCoordinator(hass, device, entry, update_interval=update_interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry to unload.

    Returns:
        bool: True if the entry was successfully unloaded.
    """
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        # PlumDevice now keeps its TCP connection open across transactions
        # (persistent connection) instead of closing it after every one --
        # tear it down explicitly here so a reload/removal doesn't leak an
        # open socket until garbage collection gets around to it.
        await asyncio.to_thread(coordinator.device.close)
    return unload_ok
