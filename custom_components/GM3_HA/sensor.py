import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure les capteurs Plum à partir d'une entrée de configuration."""
    
    # On récupère le coordinateur (le chef d'orchestre)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # On parcourt la liste théorique des capteurs (définie dans const.py)
    for slug, config in SENSOR_TYPES.items():
        # config = [Nom, Unité, Icone, DeviceClass]
        
        # Vérification 1 : Est-ce que ce paramètre est dans le mapping JSON ?
        if slug not in coordinator.device.params_map:
            continue

        # Vérification 2 : Est-ce que le coordinateur a réussi à lire une valeur ?
        # (Cela permet de filtrer les circuits inactifs qui renvoient None ou Timeout)
        if slug in coordinator.data:
            entities.append(PlumEcomaxSensor(coordinator, entry, slug, config))
        else:
            _LOGGER.debug(f"Capteur '{slug}' ignoré car aucune donnée reçue.")

    if entities:
        _LOGGER.info(f"Ajout de {len(entities)} capteurs Plum EcoMAX.")
        async_add_entities(entities)


class PlumEcomaxSensor(CoordinatorEntity, SensorEntity):
    """Représentation d'un capteur Plum (Température, Puissance, etc.)."""

    def __init__(self, coordinator, entry, slug, config):
        """Initialisation."""
        super().__init__(coordinator)
        self._slug = slug
        self._config_name = config[0]
        self._unit = config[1]
        self._icon = config[2]
        self._device_class = config[3]
        self._entry_id = entry.entry_id
        
        # Paramètre brut depuis le JSON (pour récupérer l'ID si besoin)
        self._param_def = coordinator.device.params_map.get(slug)

    @property
    def unique_id(self):
        """ID unique technique : plum_ecomax_[hash_entry]_[slug]."""
        return f"{DOMAIN}_{self._entry_id}_{self._slug}"

    @property
    def name(self):
        """Nom affiché dans Home Assistant."""
        return f"Plum {self._config_name}"

    @property
    def native_value(self):
        """La valeur actuelle retournée par le coordinateur."""
        # On lit directement dans le cache du coordinateur
        return self.coordinator.data.get(self._slug)

    @property
    def native_unit_of_measurement(self):
        """Unité (°C, %, kW...)."""
        return self._unit

    @property
    def icon(self):
        """Icône dynamique."""
        return self._icon

    @property
    def device_class(self):
        """Type de donnée (temperature, power, etc) pour l'affichage auto."""
        return self._device_class

    @property
    def state_class(self):
        """Permet d'avoir des graphiques historiques (Statistics)."""
        return SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        """Le capteur est-il disponible ?"""
        # Si le coordinateur a échoué sa dernière update globale, on passe en indispo
        return self.coordinator.last_update_success and (self._slug in self.coordinator.data)

    @property
    def device_info(self):
        """Lie ce capteur à l'appareil 'Chaudière' dans HA."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Chaudière Plum EcoMAX",
            "manufacturer": "Plum Sp. z o.o.",
            "model": "EcoMAX 360/860",
            "sw_version": "1.0",
        }
