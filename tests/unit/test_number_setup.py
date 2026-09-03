"""Unit test for number.py's async_setup_entry circuit filtering.

Regression for a real bug reported by the user: number.py was the only
platform (sensor.py/climate.py/calendar.py already did this) that ignored
CONF_ACTIVE_CIRCUITS entirely, creating heating-curve entities for every
circuit 1-7 in the device map regardless of which ones are actually wired
up in the user's installation (they only use circuit 2).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.plum_ecomax.const import CONF_ACTIVE_CIRCUITS, DOMAIN
from custom_components.plum_ecomax.number import PlumEcomaxNumber, async_setup_entry


def _make_hass_and_entry(params_map: dict, active_circuits: list[str]):
    coordinator = MagicMock()
    coordinator.device.params_map = params_map
    coordinator.data = {}

    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry123"
    entry.data = {CONF_ACTIVE_CIRCUITS: active_circuits}
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}
    return hass, entry


@pytest.mark.asyncio
async def test_only_active_circuit_numbers_are_created():
    params_map = {
        "circuit1curvefloor": {"id": 1}, "circuit1basetemp": {"id": 2},
        "circuit2curvefloor": {"id": 3}, "circuit2basetemp": {"id": 4},
        "circuit3curvefloor": {"id": 5},
        "buforlongloadtime": {"id": 6},  # not circuit-prefixed, always eligible
    }
    hass, entry = _make_hass_and_entry(params_map, active_circuits=["2"])

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    slugs = {e._slug for e in added}
    assert slugs == {"circuit2curvefloor", "circuit2basetemp", "buforlongloadtime"}
    assert "circuit1curvefloor" not in slugs
    assert "circuit3curvefloor" not in slugs


@pytest.mark.asyncio
async def test_no_active_circuits_creates_no_circuit_entities():
    params_map = {
        "circuit2curvefloor": {"id": 3},
        "buforlongloadtime": {"id": 6},
    }
    hass, entry = _make_hass_and_entry(params_map, active_circuits=[])

    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))

    slugs = {e._slug for e in added}
    assert slugs == {"buforlongloadtime"}


@pytest.mark.asyncio
async def test_async_set_native_value_does_not_truncate_floats():
    """Regression: async_set_native_value used to int()-cast the value,
    silently rounding FLOAT parameters (heating curves, step 0.1) so setting
    a curve to 1.4 wrote 1.0 to the boiler. The value must reach the
    coordinator unchanged -- PlumDevice._encode casts per wire type.
    """
    coordinator = MagicMock()
    coordinator.async_set_value = AsyncMock(return_value=True)
    entry = MagicMock()
    entry.entry_id = "e1"

    number = PlumEcomaxNumber(
        coordinator, entry, "circuit2curvefloor", (0.1, 4.0, 0.1, "mdi:chart-bell-curve")
    )
    await number.async_set_native_value(1.4)

    coordinator.async_set_value.assert_awaited_once_with("circuit2curvefloor", 1.4)
