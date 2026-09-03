"""Unit tests for the PlumEconetCalendar entity."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from custom_components.plum_ecomax.calendar import PlumEconetCalendar
from custom_components.plum_ecomax.const import DOMAIN


# --- FIX: Helper pour ajouter une timezone UTC aux datetimes naïfs ---
def mock_as_local(dt):
    """Simule dt_util.as_local en ajoutant UTC si manquant."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {}
    coord.device.params_map = {
        "circuit1mondayam": {"name": "Test"},
        "hdwmondayam": {"name": "Test DHW"},
    }
    return coord


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    return entry


def test_calendar_init_circuit(mock_coordinator, mock_entry):
    calendar = PlumEconetCalendar(mock_coordinator, mock_entry, "circuit", 1)
    # Naming now comes from has_entity_name + translation_key (like every
    # other platform here), composed with the device name by HA itself --
    # not a plain _attr_name, so it can't be asserted without a real
    # translation-loading hass. See test_unique_id_stability.py /
    # test_device_info_scoping.py for the device_info + unique_id coverage.
    assert calendar._attr_has_entity_name is True
    assert calendar._attr_translation_key == "schedule"
    assert calendar.unique_id == f"{DOMAIN}_test_entry_id_calendar_circuit_1"


def test_calendar_init_hdw(mock_coordinator, mock_entry):
    calendar = PlumEconetCalendar(mock_coordinator, mock_entry, "hdw", 0)
    assert calendar._attr_has_entity_name is True
    assert calendar._attr_translation_key == "schedule"
    assert calendar.unique_id == f"{DOMAIN}_test_entry_id_calendar_hdw"


@pytest.mark.asyncio
async def test_get_events_decoding_logic(mock_coordinator, mock_entry):
    calendar = PlumEconetCalendar(mock_coordinator, mock_entry, "circuit", 1)

    # 06:00 to 08:00 AM Comfort
    # Bits 12, 13, 14, 15 = 1 -> Value 61440
    mock_coordinator.data["circuit1mondayam"] = 61440
    mock_coordinator.data["circuit1mondaypm"] = 0

    # Dates de requête (timezone-aware pour être propre)
    start_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    end_date = datetime(2024, 1, 1, 23, 59, 59, tzinfo=UTC)

    hass = MagicMock()

    # --- CORRECTION ICI : On utilise notre fonction mock_as_local ---
    with patch(
        "custom_components.plum_ecomax.calendar.dt_util.as_local", side_effect=mock_as_local
    ):
        events = await calendar.async_get_events(hass, start_date, end_date)

    assert len(events) == 3

    # On vérifie les dates avec timezone UTC
    # Event 1: Eco 00:00 -> 06:00
    assert events[0].summary == "Eco"
    assert events[0].start == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert events[0].end == datetime(2024, 1, 1, 6, 0, tzinfo=UTC)

    # Event 2: Confort 06:00 -> 08:00
    # NOTE: Vérifiez si votre code utilise "Confort" ou "Actif".
    # J'utilise "Confort" ici comme dans votre dernière demande.
    assert events[1].summary == "Active"  # ou "Confort" selon votre code calendar.py
    assert events[1].start == datetime(2024, 1, 1, 6, 0, tzinfo=UTC)
    assert events[1].end == datetime(2024, 1, 1, 8, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_get_events_hdw_mapping(mock_coordinator, mock_entry):
    calendar = PlumEconetCalendar(mock_coordinator, mock_entry, "hdw", 0)

    mock_coordinator.data["hdwmondayam"] = 16777215  # Full AM
    mock_coordinator.data["hdwmondaypm"] = 0

    start_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    end_date = datetime(2024, 1, 1, 23, 59, 59, tzinfo=UTC)
    hass = MagicMock()

    with patch(
        "custom_components.plum_ecomax.calendar.dt_util.as_local", side_effect=mock_as_local
    ):
        events = await calendar.async_get_events(hass, start_date, end_date)

    assert len(events) == 2
    assert events[0].summary == "Active"
    assert events[0].end == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
