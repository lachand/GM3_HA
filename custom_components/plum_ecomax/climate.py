import logging
from typing import Any, Optional

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# On importe nos constantes locales
from .const import (
    DOMAIN, 
    CLIMATE_TYPES, 
    PLUM_TO_HA_PRESET, 
    HA_TO_PLUM_PRESET,
    HA_TO_PLUM_HVAC,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configuration des entités Climate."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for name, slugs in CLIMATE_TYPES.items():
        if len(slugs) == 4:
            entities.append(
                PlumEconetClimate(coordinator, entry, name, slugs[0], slugs[1], slugs[2], slugs[3])
            )
        elif len(slugs) == 3:
            _LOGGER.warning(f"Config for {name} missing Eco slug.")
            entities.append(
                PlumEconetClimate(coordinator, entry, name, slugs[0], slugs[1], None, slugs[2])
            )

    async_add_entities(entities)


class PlumEcomaxClimate(CoordinatorEntity, ClimateEntity):
    """Représentation d'un circuit de chauffage Plum."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = False 
    
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | 
        ClimateEntityFeature.PRESET_MODE |
        ClimateEntityFeature.TURN_OFF | 
        ClimateEntityFeature.TURN_ON
    )
    
    _attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_AUTO]
    _attr_preset_modes = [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

    def __init__(self, coordinator, entry, name, temp_slug, target_slug, eco_slug, mode_slug):
        """
        @param entry: ConfigEntry (passé pour récupérer l'ID si besoin, ou pour le lien device)
        """
        super().__init__(coordinator)
        self._name = name
        self._temp_slug = temp_slug
        self._target_slug = target_slug
        self._eco_slug = eco_slug
        self._mode_slug = mode_slug
        self._entry_id = entry.entry_id
        
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{target_slug}"

    @property
    def device_info(self):
        """Lie l'entité au device Home Assistant."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Plum EcoMAX",
            "manufacturer": "Plum",
        }

    @property
    def current_temperature(self) -> Optional[float]:
        return self.coordinator.data.get(self._temp_slug)

    @property
    def target_temperature(self) -> Optional[float]:
        """Consigne active (Confort ou Eco selon le preset)."""
        preset = self.preset_mode
        if preset == PRESET_ECO and self._eco_slug:
            return self.coordinator.data.get(self._eco_slug)
        return self.coordinator.data.get(self._target_slug)

    @property
    def hvac_mode(self) -> str:
        raw_mode = self.coordinator.data.get(self._mode_slug)
        
        if raw_mode == 3:
            return HVAC_MODE_AUTO
        if raw_mode in [0, 1, 2]:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @property
    def preset_mode(self) -> Optional[str]:
        raw_mode = self.coordinator.data.get(self._mode_slug)
        return PLUM_TO_HA_PRESET.get(raw_mode)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        target_value = None

        if hvac_mode == HVAC_MODE_OFF:
            target_value = HA_TO_PLUM_HVAC.get(HVAC_MODE_OFF)
        elif hvac_mode == HVAC_MODE_AUTO:
            target_value = HA_TO_PLUM_HVAC.get(HVAC_MODE_AUTO)
        elif hvac_mode == HVAC_MODE_HEAT:
            current_preset = self.preset_mode
            if current_preset == PRESET_ECO:
                target_value = 2
            elif current_preset == PRESET_AWAY:
                target_value = 1
            else:
                target_value = 1

        if target_value is not None:
            _LOGGER.info(f"Set HVAC {self._name}: {hvac_mode} -> {target_value}")
            await self.coordinator.async_set_value(self._mode_slug, target_value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        target_value = HA_TO_PLUM_PRESET.get(preset_mode)
        if target_value is not None:
            _LOGGER.info(f"Set Preset {self._name}: {preset_mode} -> {target_value}")
            await self.coordinator.async_set_value(self._mode_slug, target_value)

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        slug_to_write = self._target_slug 

        # Si on est en mode ECO, on écrit sur la consigne ECO
        if self.preset_mode == PRESET_ECO and self._eco_slug:
            slug_to_write = self._eco_slug
            _LOGGER.info(f"Set ECO temp {self._name} -> {temp}")
        elif self.preset_mode == PRESET_AWAY:
            _LOGGER.warning("Impossible de changer temp en mode Hors-gel")
            return
        else:
            _LOGGER.info(f"Set COMFORT temp {self._name} -> {temp}")

        await self.coordinator.async_set_value(slug_to_write, temp)
