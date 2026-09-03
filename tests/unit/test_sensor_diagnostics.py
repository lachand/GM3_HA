"""Unit tests for the link-health diagnostic sensors (sensor.py)."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory

from custom_components.plum_ecomax.sensor import (
    PlumConsecutiveFailuresSensor,
    PlumLastCommunicationSensor,
)


def _coordinator(last_success_ts=None, consecutive_failures=0):
    coordinator = MagicMock()
    coordinator.device.last_success_ts = last_success_ts
    coordinator.device.consecutive_failures = consecutive_failures
    coordinator.data = {}
    return coordinator


def test_last_communication_none_before_first_success():
    s = PlumLastCommunicationSensor(_coordinator(last_success_ts=None), "e1")
    assert s.native_value is None
    assert s.device_class == SensorDeviceClass.TIMESTAMP
    assert s.entity_category == EntityCategory.DIAGNOSTIC


def test_last_communication_returns_tz_aware_datetime():
    ts = 1_700_000_000.0
    s = PlumLastCommunicationSensor(_coordinator(last_success_ts=ts), "e1")
    assert s.native_value == datetime.fromtimestamp(ts, tz=UTC)
    assert s.native_value.tzinfo is not None


def test_consecutive_failures_reports_the_counter():
    s = PlumConsecutiveFailuresSensor(_coordinator(consecutive_failures=4), "e1")
    assert s.native_value == 4
    assert s.entity_category == EntityCategory.DIAGNOSTIC


def test_unique_ids_are_entry_scoped():
    a = PlumLastCommunicationSensor(_coordinator(), "entryA")
    b = PlumConsecutiveFailuresSensor(_coordinator(), "entryB")
    assert a.unique_id == "plum_ecomax_entryA_last_communication"
    assert b.unique_id == "plum_ecomax_entryB_consecutive_failures"
