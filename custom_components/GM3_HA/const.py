from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTime,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_IP_ADDRESS,
    CONF_PORT,
)

# --- CONFIGURATION SWITCH (ON/OFF) ---
# Format: "slug": "Friendly Name"
SWITCH_TYPES = {
    "hdwstartoneloading": "Force Recharge ECS",
}

# --- CONFIGURATION SELECT (DROPDOWN) ---

# Mapping specific to DHW (ECS) Mode
# 0 = Off, 1 = Manual/Constant, 2 = Schedule/Auto
DHW_MODES_TO_HA = {
    0: "off",
    1: "manual",
    2: "auto"
}

HA_TO_DHW_MODES = {
    "off": 0,
    "manual": 1,
    "auto": 2
}

# Format: "slug": ("Friendly Name", Map_To_HA, Map_To_Plum)
SELECT_TYPES = {
    "hdwusermode": ("Mode ECS", DHW_MODES_TO_HA, HA_TO_DHW_MODES),
}

# --- DÉFINITION LOCALE DES CONSTANTES (Indépendant de HA) ---
# On définit nous-mêmes les valeurs standards pour éviter tout problème d'import
HVAC_MODE_OFF = "off"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_AUTO = "auto"

PRESET_AWAY = "away"
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
# -----------------------------------------------------------

# Mapping Plum -> Home Assistant
PLUM_TO_HA_HVAC = {
    0: HVAC_MODE_HEAT, # Hors gel (0) = Chauffe active
    1: HVAC_MODE_HEAT, # Confort
    2: HVAC_MODE_HEAT, # Eco
    3: HVAC_MODE_AUTO, # Auto
}

PLUM_TO_HA_PRESET = {
    0: PRESET_AWAY,
    1: PRESET_COMFORT,
    2: PRESET_ECO,
}

# Mapping Inverse Home Assistant -> Plum
HA_TO_PLUM_HVAC = {
    HVAC_MODE_OFF: 0,
    HVAC_MODE_AUTO: 3,
}

HA_TO_PLUM_PRESET = {
    PRESET_AWAY: 0,
    PRESET_COMFORT: 1,
    PRESET_ECO: 2,
}

DOMAIN = "plum_ecomax"
DEFAULT_PORT = 8899

CONF_ACTIVE_CIRCUITS = "active_circuits"

# Mapping simplifié (Juste les clés)
CIRCUIT_CHOICES = ["1", "2", "3", "4", "5", "6", "7"]

UPDATE_INTERVAL = 30

# --- CONFIGURATION DES CAPTEURS ---
# Format: "slug": [Unité, Icone, DeviceClass] (3 éléments)
SENSOR_TYPES = {
    "tempwthr": [UnitOfTemperature.CELSIUS, "mdi:thermometer", "temperature"],
    "boilerpower": [UnitOfPower.KILO_WATT, "mdi:flash", "power"],
    "worktime": [UnitOfTime.SECONDS, "mdi:clock-outline", None],
    "tempcwu": [UnitOfTemperature.CELSIUS, "mdi:water-boiler", "temperature"],
    "tempbufordown": [UnitOfTemperature.CELSIUS, "mdi:tank", "temperature"],
    "buforsetpoint": [UnitOfTemperature.CELSIUS, "mdi:target", "temperature"],

    "tempcircuit1": [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "tempcircuit2": [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "tempcircuit3": [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "tempcircuit4": [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "tempcircuit5": [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "tempcircuit6": [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "tempcircuit7": [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    
    "circuit1thermostattemp" : [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "circuit2thermostattemp" : [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "circuit3thermostattemp" : [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "circuit4thermostattemp" : [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "circuit5thermostattemp" : [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "circuit6thermostattemp" : [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],
    "circuit7thermostattemp" : [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],

    "mixer1valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer2valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer3valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer4valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer5valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer6valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer7valveposition": [PERCENTAGE, "mdi:valve", None],
}

# --- THERMOSTATS ---
CLIMATE_TYPES = {
    "1": ["tempcircuit1", "circuit1comforttemp","circuit1ecotemp", "circuit1workstate"],
    "2": ["tempcircuit2", "circuit2comforttemp","circuit2ecotemp", "circuit2workstate"],
    "3": ["tempcircuit3", "circuit3comforttemp","circuit3ecotemp", "circuit3workstate"],
    "4": ["tempcircuit4", "circuit4comforttemp","circuit4ecotemp", "circuit4workstate"],
    "5": ["tempcircuit5", "circuit5comforttemp","circuit5ecotemp", "circuit5workstate"],
    "6": ["tempcircuit6", "circuit6comforttemp","circuit6ecotemp", "circuit6workstate"],
    "7": ["tempcircuit7", "circuit7comforttemp","circuit7ecotemp", "circuit7workstate"],
}

# --- WATER HEATER ---
WATER_HEATER_CONFIG = {
    # Nom supprimé ici, géré par clé de trad "eau_chaude_sanitaire"
    "current": "tempcwu",
    "target": "hdwtsetpoint",
    "min": "hdwminsettemp",
    "max": "hdwmaxsettemp",
}

# --- NUMBER ---
# Format: "slug": [min, max, step, Icone] (4 éléments)
NUMBER_TYPES = {
    "hdwtsetpoint": [20, 70, 1, "mdi:water-thermometer"],
    "hdwminsettemp": [10, 50, 1, "mdi:thermometer-chevron-down"],
    "hdwmaxsettemp": [50, 80, 1, "mdi:thermometer-chevron-up"],
}