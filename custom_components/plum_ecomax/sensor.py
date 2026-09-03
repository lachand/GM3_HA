"""Sensor platform for the Plum EcoMAX integration.

This module handles the creation and management of sensor entities.
It automatically detects which circuit a sensor belongs to (using regex)
and attaches it to the correct device in Home Assistant.

It also implements critical safety checks to handle 'NaN' (Not a Number)
values that might be returned by the boiler during initialization or errors.
"""

import logging
import math  # <--- CRITICAL: Import required for NaN checks
import re

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ACTIVE_CIRCUITS, DIAGNOSTIC_SENSOR_SLUGS, DOMAIN, SENSOR_TYPES
from .device import boiler_device_info, circuit_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Sets up sensor entities based on the configuration.

    Iterates through the `SENSOR_TYPES` defined in constants.
    If a sensor name contains 'circuit' or 'mixer' followed by a number,
    it is automatically assigned to that specific heating circuit device,
    provided that circuit is enabled in the configuration.

    Mixer N is physically tied to circuit N on this boiler (it's the valve
    actuator for that circuit's mix), so mixer entities are gated by the
    same active-circuits setting as circuit entities -- previously mixers
    were "always shown" regardless, which created entities like
    "Ouverture Vanne 3" for a circuit the user never configured or wired up.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.
        async_add_entities: Callback to add entities.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected_circuits = entry.data.get(CONF_ACTIVE_CIRCUITS, [])
    entities = []

    for slug, config in SENSOR_TYPES.items():
        # Skip if the parameter is not present on the device
        if slug not in coordinator.device.params_map:
            continue

        target_circuit_id = None
        # Automatic circuit detection via Regex (e.g., tempcircuit1 -> 1)
        match = re.search(r"(circuit|mixer)(\d+)", slug)

        if match:
            found_id = match.group(2)
            # Circuit and mixer sensors alike: only shown if that circuit
            # number is enabled in config.
            if found_id in selected_circuits:
                target_circuit_id = found_id
            else:
                continue

        entities.append(PlumEcomaxSensor(coordinator, entry, slug, config, target_circuit_id))

    if entities:
        async_add_entities(entities)


class PlumEcomaxSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Plum sensor entity with NaN protection.

    This entity handles both numeric and text sensors. For numeric sensors,
    it explicitly checks for valid float values and filters out
    NaN/Infinity to prevent errors in Home Assistant's recorder.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, slug, config, circuit_id=None):
        """Initializes the sensor.

        Args:
            coordinator: The data update coordinator.
            entry: The config entry.
            slug: The parameter identifier.
            config: A tuple containing (unit, icon, device_class).
            circuit_id: Optional ID to link to a specific circuit device.
        """
        super().__init__(coordinator)
        self._slug = slug
        self._attr_translation_key = slug

        # Unpack configuration from const.py
        self._unit = config[0]
        self._icon = config[1]
        self._device_class = config[2]

        self._entry_id = entry.entry_id
        self._circuit_id = circuit_id

    @property
    def unique_id(self) -> str:
        """Returns the unique ID of the sensor.

        Returns:
            str: The unique identifier.
        """
        return f"{DOMAIN}_{self._entry_id}_{self._slug}"

    @property
    def native_value(self) -> float | str | None:
        """Returns the sensor value with safety checks.

        CRITICAL FIX: Filters out 'NaN' (Not a Number) values to prevent HA crash.

        Returns:
            float | str | None: The sanitized value.
        """
        val = self.coordinator.data.get(self._slug)

        if val is None:
            return None

        # If a Device Class or Unit is defined, we expect a number
        if self._device_class or self._unit:
            try:
                f_val = float(val)
                # Check if value is NaN or Infinite -> Return None (Unavailable)
                if math.isnan(f_val) or math.isinf(f_val):
                    return None
                return f_val
            except (ValueError, TypeError):
                # Conversion failed but a number was expected -> Return None
                return None

        # For text sensors, return the value as is
        return val

    @property
    def available(self) -> bool:
        """Checks if the entity is available.

        Returns:
            bool: False if data is missing or NaN, True otherwise.
        """
        val = self.coordinator.data.get(self._slug)
        if val is None:
            return False

        # If it's a number, check for NaN
        if isinstance(val, float) and math.isnan(val):
            return False

        return super().available

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Returns the unit of measurement."""
        return self._unit

    @property
    def icon(self) -> str | None:
        """Returns the icon."""
        return self._icon

    @property
    def device_class(self) -> str | None:
        """Returns the device class."""
        return self._device_class

    @property
    def state_class(self) -> SensorStateClass | None:
        """Returns the state class (Measurement for numbers)."""
        # Only set state_class for numeric sensors
        if self._device_class or self._unit:
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def entity_category(self) -> EntityCategory | None:
        """Raw diagnostic registers (see DIAGNOSTIC_SENSOR_SLUGS) are shown
        under the device's "Diagnostic" section instead of the main card.
        """
        if self._slug in DIAGNOSTIC_SENSOR_SLUGS:
            return EntityCategory.DIAGNOSTIC
        return None

    @property
    def device_info(self) -> dict:
        """Links the sensor to the correct device (Boiler or Circuit).

        Returns:
            dict: The device info dictionary.
        """
        if self._circuit_id:
            return circuit_device_info(self._entry_id, self._circuit_id)
        return boiler_device_info(self._entry_id, self.coordinator.data.get("uid"))
