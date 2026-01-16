"""Climate platform for the Plum EcoMAX integration.

This module handles the thermostat entities for heating circuits, allowing
control over target temperatures and HVAC modes (Heat/Off). It supports
automatic fallback for temperature sensors if the thermostat sensor is missing.
"""
import logging
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ACTIVE_CIRCUITS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Sets up Plum EcoMAX climate entities based on the config entry.

    This function dynamically creates climate entities for each active circuit
    defined in the configuration. It implements a fallback mechanism for the
    current temperature sensor: if the thermostat sensor is unavailable,
    it uses the circuit temperature sensor instead.

    Args:
        hass: The Home Assistant instance.
        entry: The configuration entry.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected_circuits = entry.data.get(CONF_ACTIVE_CIRCUITS, [])
    entities = []

    for circuit_id in selected_circuits:
        current_slug = f"circuit{circuit_id}thermostattemp"
        target_slug = f"circuit{circuit_id}comforttemp"
        active_slug = f"circuit{circuit_id}active"
        
        # Fallback sonde
        if current_slug not in coordinator.device.params_map:
             current_slug = f"tempcircuit{circuit_id}"

        if target_slug in coordinator.device.params_map:
             entities.append(PlumEcomaxClimate(
                 coordinator, entry, circuit_id, current_slug, target_slug, active_slug
            ))

    if entities:
        async_add_entities(entities)

class PlumEcomaxClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Plum EcoMAX heating circuit thermostat.

    This entity controls the heating parameters for a specific circuit.
    It links to the device coordinator to read/write values such as
    target temperature and active state.
    """
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    
    # CLÉ DE TRADUCTION
    _attr_translation_key = "thermostat"

    def __init__(self, coordinator, entry, circuit_id, current_slug, target_slug, active_slug):
        """Initializes the climate entity.

        Args:
            coordinator: The data update coordinator.
            entry: The config entry.
            circuit_id: The ID of the circuit (e.g., 1, 2).
            current_slug: The slug for the current temperature sensor.
            target_slug: The slug for the target temperature parameter.
            active_slug: The slug for the active state parameter.
        """
        super().__init__(coordinator)
        self._circuit_id = circuit_id
        self._entry_id = entry.entry_id
        self._current_slug = current_slug
        self._target_slug = target_slug
        self._active_slug = active_slug

    @property
    def unique_id(self):
        """Returns a unique ID for the climate entity.

        Returns:
            str: The unique identifier string.
        """
        return f"{DOMAIN}_{self._entry_id}_circuit_{self._circuit_id}_climate"

    @property
    def device_info(self):
        """Links the entity to the device registry.

        Returns:
            dict: Device info dictionary.
        """
        return {
            "identifiers": {(DOMAIN, f"{self._entry_id}_circuit_{self._circuit_id}")},
            "name": f"Circuit {self._circuit_id}",
            "manufacturer": "Plum",
            "model": "Heating controller",
            "via_device": (DOMAIN, self._entry_id),
        }

    @property
    def min_temp(self): 
        """Returns the minimum target temperature."""
        return 10.0
    @property
    def max_temp(self): 
        """Returns the maximum target temperature."""
        return 30.0
    @property
    def target_temperature_step(self): 
        """Returns the step size for target temperature."""
        return 0.5

    @property
    def current_temperature(self):
        """Returns the current temperature.

        Returns:
            float | None: The current temperature or None if unavailable.
        """
        val = self.coordinator.data.get(self._current_slug)
        return float(val) if val is not None else None

    @property
    def target_temperature(self):
        """Returns the temperature we try to reach.

        Returns:
            float: The target temperature.
        """
        val = self.coordinator.data.get(self._target_slug)
        if val is None: return 20.0 
        return float(val)

    @property
    def hvac_mode(self):
        """Returns current operation mode (Heat or Off).

        Returns:
            HVACMode: The current mode.
        """
        is_active = self.coordinator.data.get(self._active_slug)
        if is_active == 0: return HVACMode.OFF
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode):
        """Sets new target operation mode.

        Args:
            hvac_mode: The desired HVAC mode.
        """
        value = 1 if hvac_mode == HVACMode.HEAT else 0
        if await self.coordinator.device.set_value(self._active_slug, value):
            self.coordinator.data[self._active_slug] = value
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Sets new target temperature.

        If the device is currently Off, it will be switched to Heat mode automatically.

        Args:
            **kwargs: Keyword arguments containing ATTR_TEMPERATURE.
        """
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None: return
        if self.hvac_mode == HVACMode.OFF:
            await self.async_set_hvac_mode(HVACMode.HEAT)
        
        if await self.coordinator.device.set_value(self._target_slug, temp):
            self.coordinator.data[self._target_slug] = temp
            self.async_write_ha_state()
        else:
            await self.coordinator.async_request_refresh()