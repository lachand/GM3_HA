"""Constants and Configuration Maps for Plum EcoMAX.

This module defines all the constant values, mapping dictionaries, and
configuration schemas used throughout the integration. It acts as the
central repository for:

* **Domain & Defaults**: Integration domain and default connection ports.
* **Mappings**: Translation maps between Plum device codes and Home Assistant states (HVAC, Presets).
* **Entity Definitions**: Configuration dictionaries for Sensors, Climates, Switches, etc.
* **Unit Definitions**: Standard units imported from Home Assistant.

Attributes:
    DOMAIN (str): The integration domain ('plum_ecomax').
    DEFAULT_PORT (int): The default TCP port for the ecoNET module (8899).
    CONF_ACTIVE_CIRCUITS (str): Configuration key for active heating circuits.
    UPDATE_INTERVAL (int): Polling interval in seconds (30).
    PLUM_TO_HA_HVAC (dict): Mapping from Plum WorkMode (0-3) to HA HVAC Modes.
    SENSOR_TYPES (dict): Definitions of available sensors [Unit, Icon, DeviceClass].
"""
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
    # Format: "slug": (friendly_name, on_value, off_value)
    "hdwstartoneloading": ("Force DHW reload", 1, 0),
    # 0x200 = bit 9 levé = marche forcée pompe ECS vers ballon solaire (ID 172)
    "hdwpumpforce": ("Force pompe ECS → ballon solaire", 512, 0),
    "hdwstartlegion": ("Cycle anti-légionellose", 1, 0),
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
    "hdwusermode": ("DHW Mode", DHW_MODES_TO_HA, HA_TO_DHW_MODES),
}

# --- LOCAL CONSTANT DEFINITIONS (Independent of HA) ---
# We define our own standard values to avoid any import issues
HVAC_MODE_OFF = "off"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_AUTO = "auto"

PRESET_AWAY = "away"
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
# -----------------------------------------------------------

# Mapping Plum -> Home Assistant
PLUM_TO_HA_HVAC = {
    0: HVAC_MODE_HEAT, # Frost protection (0) = Active heating
    1: HVAC_MODE_HEAT, # Comfort
    2: HVAC_MODE_HEAT, # Eco
    3: HVAC_MODE_AUTO, # Auto
}

PLUM_TO_HA_PRESET = {
    0: PRESET_AWAY,
    1: PRESET_COMFORT,
    2: PRESET_ECO,
}

# Inverse Mapping Home Assistant -> Plum
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

# Simplified Mapping (Just the keys)
CIRCUIT_CHOICES = ["1", "2", "3", "4", "5", "6", "7"]

UPDATE_INTERVAL = 30

# --- PARAMETERS USED IN DEVICE REGISTRY METADATA, NOT AS ENTITIES ---
# Still need to be polled into coordinator.data so device_info properties
# can read them (see device.py's boiler_device_info(serial_number=...)).
DEVICE_INFO_PARAMS = ["uid"]

# --- SENSOR CONFIGURATION ---
# Format: "slug": [Unit, Icon, DeviceClass] (3 elements)
SENSOR_TYPES = {
    "tempwthr": [UnitOfTemperature.CELSIUS, "mdi:thermometer", "temperature"],
    "boilerpower": [UnitOfPower.KILO_WATT, "mdi:flash", "power"],
    "tempcwu": [UnitOfTemperature.CELSIUS, "mdi:water-boiler", "temperature"],
    "hdwpumpstate": [None, "mdi:pump", None],
    "tempbuforup": [UnitOfTemperature.CELSIUS, "mdi:water", "temperature"],
    "tempbufordown": [UnitOfTemperature.CELSIUS, "mdi:water", "temperature"],
    "tempclutch": [UnitOfTemperature.CELSIUS, "mdi:fire-alert", "temperature"],
    "buforsetpoint": [UnitOfTemperature.CELSIUS, "mdi:target", "temperature"],

    # No "tempcircuit1": circuit 1 has no dedicated flow-temp register in
    # the device map (id sequence 61,62,63,64,65,[gap],66=tempcircuit2,67=
    # tempcircuit3,...) -- circuit 1's room temperature is already covered
    # via circuit1thermostattemp, and climate.py's own fallback chain
    # doesn't need this slug either. See IMPROVEMENT_PLAN.md.
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
    # No "circuit6thermostattemp" in the device map either -- climate.py's
    # fallback chain (circuitNthermostattemp -> tempcircuitN) already
    # covers circuit 6 via tempcircuit6, this was only a dead sensor entry.
    "circuit7thermostattemp" : [UnitOfTemperature.CELSIUS, "mdi:radiator", "temperature"],

    "mixer1valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer2valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer3valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer4valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer5valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer6valveposition": [PERCENTAGE, "mdi:valve", None],
    "mixer7valveposition": [PERCENTAGE, "mdi:valve", None],

    # RAW/STRING parameters (device.py's RAW decode, DP_INVENTORY.md).
    # "uid" is deliberately NOT a sensor -- device.py's boiler_device_info()
    # shows it as the device registry's serial_number instead. It's kept
    # polled via DEVICE_INFO_PARAMS below.
    "circuit1name": [None, "mdi:label-outline", None],
    "circuit2name": [None, "mdi:label-outline", None],
    "circuit3name": [None, "mdi:label-outline", None],
    "circuit4name": [None, "mdi:label-outline", None],
    "circuit5name": [None, "mdi:label-outline", None],
    "circuit6name": [None, "mdi:label-outline", None],
    "circuit7name": [None, "mdi:label-outline", None],
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

NUMBER_TYPES = {
    # Force buffer tank loading for N minutes (0 = disabled)
    # Bypasses the normal temperature comparison logic (useful for solar pre-heating)
    "buforlongloadtime": (0, 180, 1, "mdi:timer"),

    # Anti-legionella cycle (DP_INVENTORY.md)
    "hdwlegionsetpoint": (60, 80, 1, "mdi:bacteria-outline"),
    "hdwlegionday": (0, 7, 1, "mdi:calendar"),
    "hdwlegionhour": (0, 23, 1, "mdi:clock-outline"),
}

# Per-circuit heating curve tuning (DP_INVENTORY.md "Circuits — courbes de
# chauffe & limites"). Circuit 6's device map has no curvefloor/curveradiator
# entries (only circuits 1-5 and 7 do), so it's skipped for those two.
for _circuit_id in range(1, 8):
    if _circuit_id != 6:
        NUMBER_TYPES[f"circuit{_circuit_id}curvefloor"] = (0.1, 4.0, 0.1, "mdi:chart-bell-curve")
        NUMBER_TYPES[f"circuit{_circuit_id}curveradiator"] = (0.1, 4.0, 0.1, "mdi:chart-bell-curve")
    NUMBER_TYPES[f"circuit{_circuit_id}basetemp"] = (20, 90, 1, "mdi:thermometer")
    NUMBER_TYPES[f"circuit{_circuit_id}tempreduction"] = (0, 15, 1, "mdi:thermometer-minus")


WEEKDAY_TO_SLUGS = {
    0: ("mondayam", "mondaypm"),
    1: ("tuesdayam", "tuesdaypm"),
    2: ("wednesdayam", "wednesdaypm"),
    3: ("thursdayam", "thursdaypm"),
    4: ("fridayam", "fridaypm"),
    5: ("saturdayam", "saturdaypm"),
    6: ("sundayam", "sundaypm")
}

# --- WATER HEATER CONFIGURATION ---
# Format: "Name": (Current_Temp, Setpoint, Min, Max, Mode_Slug, Force_Slug)
WATER_HEATER_TYPES = {
    "hdw": (
        "tempcwu",           # Current temperature
        "hdwtsetpoint",        # Setpoint
        "hdwminsettemp",     # Min bound
        "hdwmaxsettemp",     # Max bound
        "hdwusermode",       # Mode (0=Off, 1=Manual, 2=Auto)
    )
}

# Mapping Plum modes to Home Assistant Water Heater
# Off = Off
# Manual = Performance (or Gas/Electric)
# Auto = Eco
PLUM_TO_HA_WATER_HEATER = {
    0: "off",
    1: "performance", # Considered as "Manual / Permanent Comfort"
    2: "eco"          # Considered as "Auto / Schedule"
}

HA_TO_PLUM_WATER_HEATER = {
    "off": 0,
    "performance": 1,
    "eco": 2
}

# Mapping for calendar
WEEKDAY_TO_SLUGS = {
    0: ("mondayam", "mondaypm"),
    1: ("tuesdayam", "tuesdaypm"),
    2: ("wednesdayam", "wednesdaypm"),
    3: ("thursdayam", "thursdaypm"),
    4: ("fridayam", "fridaypm"),
    5: ("saturdayam", "saturdaypm"),
    6: ("sundayam", "sundaypm"),
}

SCHEDULE_TYPES = {}
for i in range(1, 8): # Circuits 1 to 7
    for day_id, (suffix_am, suffix_pm) in WEEKDAY_TO_SLUGS.items():
        slug_am = f"circuit{i}{suffix_am}"
        slug_pm = f"circuit{i}{suffix_pm}"
        SCHEDULE_TYPES[slug_am] = f"Circuit {i} AM"
        SCHEDULE_TYPES[slug_pm] = f"Circuit {i} PM"

for day_id, (suffix_am, suffix_pm) in WEEKDAY_TO_SLUGS.items():
    slug_am = f"hdw{suffix_am}"
    slug_pm = f"hdw{suffix_pm}"
    SCHEDULE_TYPES[slug_am] = "DHW AM"
    SCHEDULE_TYPES[slug_pm] = "DHW PM"