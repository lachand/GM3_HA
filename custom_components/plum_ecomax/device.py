"""Shared device-registry helpers for the Plum EcoMAX integration.

Every platform (sensor, climate, calendar, number, switch, select,
water_heater) groups its entities under one of a few devices: the main
boiler, the DHW manager, a heating circuit, or the mixers group. This
module is the single place that builds those `DeviceInfo` objects so all
platforms agree on the same identifiers.

All identifiers are scoped by config entry ID. Before this module existed,
several platforms (switch.py, calendar.py, water_heater.py) hardcoded the
DHW device as `(DOMAIN, "plum_hdw")` -- a fixed string shared by *every*
config entry, so a second boiler (second config entry) would collide with
the first on the same DHW device. `tests/regression/test_device_info_scoping.py`
guards against that pattern coming back.
"""
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN


def boiler_device_info(entry_id: str, serial_number: str | None = None) -> DeviceInfo:
    """The main boiler device.

    Args:
        entry_id: The config entry ID.
        serial_number: The boiler's serial number (device map slug "uid",
            RAW/STRING type), if the coordinator has read it yet. Shown in
            the device registry instead of as a separate sensor entity.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Plum EcoMAX Boiler",
        manufacturer="Plum",
        serial_number=serial_number,
    )


def hdw_device_info(entry_id: str) -> DeviceInfo:
    """The domestic hot water (DHW) device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_hdw")},
        name="DHW",
        manufacturer="Plum",
        model="DHW Manager",
        via_device=(DOMAIN, entry_id),
    )


def circuit_device_info(entry_id: str, circuit_id) -> DeviceInfo:
    """A heating circuit device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_circuit_{circuit_id}")},
        name=f"Circuit {circuit_id}",
        manufacturer="Plum",
        model="Heating controller",
        via_device=(DOMAIN, entry_id),
    )


def mixers_device_info(entry_id: str) -> DeviceInfo:
    """The mixing valves device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_mixers")},
        name="Mixers",
        manufacturer="Plum",
        model="Mixing valves",
        via_device=(DOMAIN, entry_id),
    )
