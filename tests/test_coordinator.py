"""Unit tests for the PlumDataUpdateCoordinator."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from custom_components.plum_ecomax.coordinator import PlumDataUpdateCoordinator

# Mock class to simulate the PlumDevice behavior
class MockDevice:
    def __init__(self):
        # We simulate a params_map with mixed configurations
        self.params_map = {
            "temp_strict_json": {"min": 10, "max": 50, "name": "Strict"},  # Has JSON limits
            "temp_generic": {"name": "Generic"},                           # No JSON limits
            "pressure_bar": {"name": "Pressure"},                          # Should use generic pressure limits
        }
        # Mock methods
        self.get_value = AsyncMock()
        self.set_value = AsyncMock()

@pytest.fixture
def coordinator(hass):
    """Fixture to create a coordinator instance with a mocked device."""
    device = MockDevice()
    coord = PlumDataUpdateCoordinator(hass, device)
    # Pre-fill cache to simulate previous state
    coord._cache = {"temp_strict_json": 20} 
    return coord

def test_validate_value_protocol_errors(coordinator):
    """Test rejection of protocol specific error codes."""
    # Test None (No data)
    valid, val = coordinator._validate_value("temp_generic", None, 20)
    assert valid is False
    assert val is None

    # Test 999 (Sensor Error)
    valid, val = coordinator._validate_value("temp_generic", 999.0, 20)
    assert valid is False
    assert val is None

def test_validate_value_json_priority(coordinator):
    """Test that JSON limits defined in params_map take priority."""
    slug = "temp_strict_json"
    
    # 1. Value inside JSON limits [10, 50]
    valid, val = coordinator._validate_value(slug, 25, 20)
    assert valid is True
    assert val == 25

    # 2. Value outside JSON limits (e.g., 60)
    # Even if 60 is valid for generic temp (-20 to 100), JSON max is 50.
    valid, val = coordinator._validate_value(slug, 60, 20)
    assert valid is False
    assert val is None

def test_validate_value_generic_fallback(coordinator):
    """Test that generic VALIDATION_RANGES are used when no JSON limits exist."""
    slug = "temp_generic" # Contains "temp", so uses (-20, 100) range
    
    # 1. Valid generic value
    valid, val = coordinator._validate_value(slug, 85, 20)
    assert valid is True
    assert val == 85

    # 2. Invalid generic value (out of -20..100)
    valid, val = coordinator._validate_value(slug, 150, 20)
    assert valid is False
    assert val is None

def test_validate_value_pressure(coordinator):
    """Test generic limits for pressure (0.0 to 4.0 bar)."""
    slug = "pressure_bar"
    
    # Valid
    valid, val = coordinator._validate_value(slug, 1.5, 1.0)
    assert valid is True
    
    # Invalid (Safety valve open?)
    valid, val = coordinator._validate_value(slug, 5.5, 1.0)
    assert valid is False
