"""Select platform for the Plum EcoMAX integration.

This module handles dropdown selection entities (SelectEntity). It is used
for parameters that have a discrete set of options, such as the DHW mode
(Off, Manual, Auto) or other enumerated settings.
"""
import logging
from typing import Any, Dict
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SELECT_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up Plum select entities (Dropdowns).

    Iterates through the `SELECT_TYPES` configuration and creates an entity
    if the corresponding parameter exists on the device.

    Args:
        hass: The Home Assistant instance.
        entry: The configuration entry.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # Config format: "slug": ("Name", Map_To_HA, Map_To_Plum)
    for slug, (name, map_to_ha, map_to_plum) in SELECT_TYPES.items():
        if slug in coordinator.device.params_map:
            entities.append(PlumEconetSelect(coordinator, slug, name, map_to_ha, map_to_plum))
        else:
            _LOGGER.debug(f"Select '{slug}' not found in device map, skipping.")

    async_add_entities(entities)

class PlumEconetSelect(CoordinatorEntity, SelectEntity):
    """Representation of a multi-choice parameter (Enum).

    This entity represents a selectable parameter on the Plum device,
    mapping internal integer values to human-readable string options
    (e.g., mapping 0->'Off', 1->'Manual').
    """

    def __init__(self, coordinator, slug: str, name: str, map_to_ha: Dict[int, str], map_to_plum: Dict[str, int]):
        """Initializes the select entity.

        Args:
            coordinator: The data update coordinator.
            slug: The parameter identifier string.
            name: The friendly name of the entity.
            map_to_ha: Dictionary mapping Integer (Plum) -> String (Home Assistant).
            map_to_plum: Dictionary mapping String (Home Assistant) -> Integer (Plum).
        """
        super().__init__(coordinator)
        self._slug = slug
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{slug}"
        self._attr_has_entity_name = False
        
        self._map_to_ha = map_to_ha
        self._map_to_plum = map_to_plum
        
        # Define available options based on the mapping keys
        self._attr_options = list(map_to_plum.keys())

    @property
    def current_option(self) -> str | None:
        """Returns the currently selected option.

        Converts the raw integer value received from the device into a
        human-readable string using the internal mapping.

        Returns:
            str | None: The selected option string, or None if unknown.
        """
        raw_val = self.coordinator.data.get(self._slug)
        try:
            raw_int = int(raw_val)
            return self._map_to_ha.get(raw_int)
        except (ValueError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Updates the selected option.

        Converts the selected string back to the corresponding integer value
        and writes it to the device via the coordinator.

        Args:
            option: The option selected by the user.
        """
        target_val = self._map_to_plum.get(option)
        
        if target_val is not None:
            _LOGGER.info(f"Setting {self._attr_name} to {option} (Raw: {target_val})")
            await self.coordinator.async_set_value(self._slug, target_val)
        else:
            _LOGGER.error(f"Invalid option '{option}' for {self._slug}")