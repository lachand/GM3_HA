"""Unit tests for Sensor entities."""
import pytest
from unittest.mock import MagicMock
import math
from homeassistant.components.sensor import SensorDeviceClass
from custom_components.plum_ecomax.sensor import PlumEcomaxSensor
from custom_components.plum_ecomax.const import DOMAIN

@pytest.fixture
def mock_coordinator():
    """Create a basic mock coordinator."""
    coord = MagicMock()
    coord.data = {}
    coord.device.params_map = {
        "temp_test": {"name": "Test Temp"},
        "fan_test": {"name": "Test Fan"},
        "unknown_thing": {"name": "Unknown"}
    }
    return coord

@pytest.fixture
def mock_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {}
    return entry

def test_sensor_nan_protection(mock_coordinator, mock_entry):
    """Test that NaN values do not crash the sensor and return None."""
    slug = "temp_test"
    # Config: Unit, Icon, DeviceClass
    config = ("°C", "mdi:thermometer", SensorDeviceClass.TEMPERATURE)
    
    sensor = PlumEcomaxSensor(mock_coordinator, mock_entry, slug, config)
    
    # 1. Test Valid Value
    mock_coordinator.data[slug] = 45.5
    assert sensor.native_value == 45.5
    assert sensor.available is True

    # 2. Test NaN Value (The Crash Fix)
    mock_coordinator.data[slug] = float('nan')
    assert sensor.native_value is None
    assert sensor.available is False

    # 3. Test Infinite Value
    mock_coordinator.data[slug] = float('inf')
    assert sensor.native_value is None

def test_sensor_device_info(mock_coordinator, mock_entry):
    """Test that device info is correctly built."""
    slug = "temp_test"
    config = ("°C", "mdi:thermometer", None)
    
    # Case 1: Global Sensor (No circuit ID)
    sensor = PlumEcomaxSensor(mock_coordinator, mock_entry, slug, config)
    dev_info = sensor.device_info
    assert dev_info["name"] == "Plum EcoMAX Boiler"
    
    # Case 2: Circuit Sensor
    sensor_circuit = PlumEcomaxSensor(mock_coordinator, mock_entry, slug, config, circuit_id=1)
    dev_info_c = sensor_circuit.device_info
    assert dev_info_c["name"] == "Circuit 1"
    # Check if it is linked via the main device
    assert dev_info_c["via_device"] == (DOMAIN, "test_entry_id")
