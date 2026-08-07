"""Number platform for the Plum EcoMAX integration.

This module provides number entities for configurable numerical parameters
of the boiler, such as hysteresis, target temperatures (if not covered by climate),
or other adjustable settings defined in `NUMBER_TYPES`.
"""
import logging
import re
from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, NUMBER_TYPES, CONF_ACTIVE_CIRCUITS
from .device import boiler_device_info, circuit_device_info, hdw_device_info, mixers_device_info

_LOGGER = logging.getLogger(__name__)

_CIRCUIT_SLUG_RE = re.compile(r"^circuit(\d+)")

# Advanced/rarely-touched settings (heating curves, anti-legionella cycle,
# forced buffer loading): moved out of the main "Controls" card into the
# device's "Configuration" section, so they aren't sitting next to everyday
# controls where they could be nudged by accident.
_ADVANCED_NUMBER_PREFIXES = ("hdwlegion", "buforlongloadtime")

async def async_setup_entry(hass, entry, async_add_entities):
    """Sets up Plum EcoMAX number entities.

    Iterates through the `NUMBER_TYPES` configuration and creates an entity
    if the corresponding parameter exists on the device. Per-circuit
    entities (heating curves etc.) are skipped for circuits not selected in
    CONF_ACTIVE_CIRCUITS -- matching sensor.py/climate.py/calendar.py, which
    already do this. Previously this platform ignored the setting entirely
    and created every circuit 1-7's entities regardless of which ones are
    actually wired up.

    Args:
        hass: The Home Assistant instance.
        entry: The configuration entry.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected_circuits = entry.data.get(CONF_ACTIVE_CIRCUITS, [])
    entities = []
    for slug, config in NUMBER_TYPES.items():
        if slug not in coordinator.device.params_map:
            continue
        circuit_match = _CIRCUIT_SLUG_RE.match(slug)
        if circuit_match and circuit_match.group(1) not in selected_circuits:
            continue
        entities.append(PlumEcomaxNumber(coordinator, entry, slug, config))
    if entities:
        async_add_entities(entities)

class PlumEcomaxNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Plum EcoMAX numerical parameter.

    This entity allows the user to adjust a numerical value (e.g., setpoint,
    hysteresis) within a defined range (min, max, step). It reflects changes
    immediately in the UI via the coordinator's optimistic update logic.
    """
    _attr_has_entity_name = True 

    def __init__(self, coordinator, entry, slug, config):
        """Initializes the number entity.

        Args:
            coordinator: The data update coordinator.
            entry: The config entry.
            slug: The parameter identifier string.
            config: A tuple containing (min, max, step, icon).
        """
        super().__init__(coordinator)
        self._slug = slug
        
        # --- INDEX CHANGE ---
        self._min_val = config[0]
        self._max_val = config[1]
        self._step_val = config[2]
        self._icon_val = config[3]
        
        self._entry_id = entry.entry_id
        self._attr_translation_key = slug

        self._circuit_match = _CIRCUIT_SLUG_RE.match(slug)
        if self._circuit_match or slug.startswith(_ADVANCED_NUMBER_PREFIXES):
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def device_info(self) -> dict:
        """Links the entity to its Circuit, DHW, Mixers, or the main Boiler device.

        Previously every non-"mixer" slug fell through to the generic
        boiler device -- including per-circuit heating curves and DHW
        settings -- which is why they all showed up crammed onto "Plum
        EcoMAX Boiler" instead of their own Circuit N / DHW device.
        """
        if self._circuit_match:
            return circuit_device_info(self._entry_id, int(self._circuit_match.group(1)))
        if self._slug.startswith("mixer"):
            return mixers_device_info(self._entry_id)
        if self._slug.startswith("hdw"):
            return hdw_device_info(self._entry_id)
        return boiler_device_info(self._entry_id, self.coordinator.data.get("uid"))

    @property
    def unique_id(self) -> str:
        """Returns the unique ID of the entity.

        Returns:
            str: The unique identifier.
        """
        return f"{DOMAIN}_{self._entry_id}_number_{self._slug}"

    @property
    def native_value(self):
        """Returns the current value of the number.

        Returns:
            float | None: The current value or None if unavailable.
        """
        val = self.coordinator.data.get(self._slug)
        return float(val) if val is not None else None

    @property
    def native_min_value(self) -> float:
        """Returns the minimum allowed value."""
        return self._min_val

    @property
    def native_max_value(self) -> float:
        """Returns the maximum allowed value."""
        return self._max_val

    @property
    def native_step(self) -> float:
        """Returns the step increment."""
        return self._step_val

    @property
    def icon(self) -> str:
        """Returns the icon for the entity."""
        return self._icon_val

    async def async_set_native_value(self, value: float) -> None:
        """Sets a new value for the entity.

        Args:
            value: The new value to set.
        """
        await self.coordinator.async_set_value(self._slug, int(value))