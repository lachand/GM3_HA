import logging
import asyncio
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

from .const import DOMAIN, CLIMATE_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configuration des thermostats."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for name, slugs in CLIMATE_TYPES.items():
        current_temp_slug = slugs[0]
        target_temp_slug = slugs[1]

        # On vérifie que les DEUX paramètres (Actuel et Consigne) existent dans le mapping
        if (target_temp_slug in coordinator.device.params_map and 
            current_temp_slug in coordinator.device.params_map):
            
            # On vérifie aussi qu'on reçoit bien des données (pour éviter les circuits fantômes)
            # On est permissif : si au moins la consigne est lue, on affiche le thermostat
            if target_temp_slug in coordinator.data:
                entities.append(PlumEcomaxClimate(coordinator, name, current_temp_slug, target_temp_slug))
            else:
                _LOGGER.debug(f"Thermostat {name} ignoré (pas de données sur {target_temp_slug})")

    if entities:
        _LOGGER.info(f"Ajout de {len(entities)} thermostats Plum.")
        async_add_entities(entities)


class PlumEcomaxClimate(CoordinatorEntity, ClimateEntity):
    """Représentation d'un circuit de chauffage Plum."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.HEAT] # On simplifie : toujours en mode Chauffage
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, name, current_slug, target_slug):
        super().__init__(coordinator)
        self._name_suffix = name
        self._current_slug = current_slug
        self._target_slug = target_slug
        self._entry_id = coordinator.config_entry.entry_id
        
        # Définition des bornes (Min/Max)
        # Idéalement, on devrait lire "circuitXminsettemprad" dans le JSON
        # Pour l'instant, on met des valeurs de sécurité standard
        self._attr_min_temp = 10
        self._attr_max_temp = 30

    @property
    def unique_id(self):
        """ID unique stable."""
        return f"{DOMAIN}_{self._entry_id}_climate_{self._target_slug}"

    @property
    def name(self):
        """Nom de l'entité."""
        return f"Thermostat {self._name_suffix}"

    @property
    def current_temperature(self):
        """Température actuelle mesurée."""
        return self.coordinator.data.get(self._current_slug)

    @property
    def target_temperature(self):
        """Consigne actuelle."""
        return self.coordinator.data.get(self._target_slug)

    @property
    def hvac_mode(self):
        """Mode actuel (Simulé à Heat pour l'instant)."""
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode):
        """Changement de mode (Non supporté réellement, on reste en Heat)."""
        if hvac_mode != HVACMode.HEAT:
            _LOGGER.warning("Seul le mode HEAT est supporté pour le moment.")

    async def async_set_temperature(self, **kwargs):
        """Définir la nouvelle température de consigne."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        _LOGGER.info(f"Demande de changement {self.name} -> {temp}")

        # 1. Envoi de la commande à la chaudière
        # On récupère le mot de passe depuis la config (si vous l'avez ajouté) ou par défaut
        # Pour l'instant on utilise le défaut user/pass du driver
        success = await self.coordinator.device.set_value(self._target_slug, temp)

        if success:
            # 2. Mise à jour Optimiste
            # On force la valeur dans le cache local du coordinateur pour que l'UI se mette à jour
            # instantanément, sans attendre le prochain cycle de lecture de 30s.
            self.coordinator.data[self._target_slug] = temp
            self.async_write_ha_state() # Force le rafraîchissement de l'entité dans HA
            _LOGGER.info(f"Consigne {self.name} mise à jour avec succès.")
        else:
            _LOGGER.error(f"Échec de la modification de consigne pour {self.name}")
            # En cas d'échec, on demande au coordinateur de relire les vraies valeurs
            await self.coordinator.async_request_refresh()
