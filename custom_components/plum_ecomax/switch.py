"""Switch platform for the Plum EcoMAX integration.

This module handles binary switch entities. These are typically used for
boolean parameters or simple on/off commands on the boiler, such as
forcing the Domestic Hot Water (DHW) heating cycle.
"""
import logging
from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCH_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up Plum switch entities.

    Iterates through the `SWITCH_TYPES` configuration and creates an entity
    if the corresponding parameter exists on the device.

    Args:
        hass: The Home Assistant instance.
        entry: The configuration entry.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for slug, name in SWITCH_TYPES.items():
        # We only create the entity if the parameter exists on the device
        if slug in coordinator.device.params_map:
            entities.append(PlumEconetSwitch(coordinator, slug, name))
        else:
            _LOGGER.debug(f"Switch '{slug}' not found in device map, skipping.")

    async_add_entities(entities)

class PlumEconetSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a binary switch.

    This entity represents a writable boolean parameter on the device.
    It uses the data coordinator to read the current state and write
    changes back to the device (e.g., setting a value of 1 for On and 0 for Off).
    """

    def __init__(self, coordinator, slug: str, name: str):
        """Initializes the switch entity.

        Args:
            coordinator: The data update coordinator.
            slug: The parameter identifier string.
            name: The friendly name of the switch.
        """
        super().__init__(coordinator)
        self._slug = slug
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{slug}"
        self._attr_has_entity_name = False

    @property
    def is_on(self) -> bool:
        """Checks if the switch is currently on.

        Returns:
            bool: True if the parameter value is 1, False otherwise.
        """
        val = self.coordinator.data.get(self._slug)
        try:
            return int(val) == 1
        except (ValueError, TypeError):
            return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turns the switch on.

        Writes '1' to the corresponding device parameter and updates the
        local cache immediately.

        Args:
            **kwargs: Keyword arguments (unused).
        """
        _LOGGER.info(f"Turning ON {self._attr_name} ({self._slug})")
        await self.coordinator.async_set_value(self._slug, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turns the switch off.

        Writes '0' to the corresponding device parameter and updates the
        local cache immediately.

        Args:
            **kwargs: Keyword arguments (unused).
        """
        _LOGGER.info(f"Turning OFF {self._attr_name} ({self._slug})")
        await self.coordinator.async_set_value(self._slug, 0)