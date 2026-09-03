"""plum_ecomax.solar_to_buffer — bank solar-heated DHW into the buffer tanks.

Use case: an overcast spell is forecast, so before it arrives you want to
move the heat currently sitting in the solar-charged DHW tank into the
(larger) buffer tanks where it stays useful for heating.

Doing that means running the DHW transfer pump, which the boiler's
automatic logic won't do on its own -- exactly what the ecoSTER's "manual
control" service screen is for. Bus capture (IMPROVEMENT_PLAN.md section N)
showed that screen does just two writes:

    operating mode (pid 161) = 2   -> manual control
    hdwpumpforce   (pid 172) = 512 -> force the DHW pump

and reverses them (161 = 1, 172 = 0) on exit. This service replays that,
holds it for a capped duration, and *guarantees* the return to automatic --
on the timer, on a second call, on integration unload, and on HA shutdown.

Manual mode disables the boiler's automatic regulation while it's active,
so the guaranteed-restore matters: a stuck manual mode means no heating
control until someone notices.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import voluptuous as vol
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import issue_registry as ir

from .const import (
    DOMAIN,
    MANUAL_MODE_BIT,
    MANUAL_MODE_SLUG,
    OPERATING_MODE_AUTO,
    OPERATING_MODE_MANUAL,
    OPERATING_MODE_SLUG,
    SOLAR_DUMP_FORCE_SLUG,
    SOLAR_DUMP_FORCE_VALUE,
    SOLAR_DUMP_MAX_MINUTES,
)
from .issues import clear_issue, raise_issue

_LOGGER = logging.getLogger(__name__)

SERVICE_SOLAR_TO_BUFFER = "solar_to_buffer"
STUCK_ISSUE_ID = "manual_mode_stuck"

SOLAR_TO_BUFFER_SCHEMA = vol.Schema(
    {
        # No upper bound here on purpose: a longer request is clamped to
        # SOLAR_DUMP_MAX_MINUTES in the handler rather than rejected.
        vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)

# entry_id -> the running lifecycle task. One dump at a time per boiler.
_RUNNING: dict[str, asyncio.Task] = {}
_STOP_UNSUB = None


async def _confirmed_write(dev, slug: str, value: int, tries: int = 3) -> bool:
    """Write and wait for the boiler's own confirmation, retrying."""
    for attempt in range(1, tries + 1):
        if await dev.set_value(slug, value):
            return True
        _LOGGER.debug("solar_to_buffer: write %s=%s not confirmed (try %d)", slug, value, attempt)
        await asyncio.sleep(1.0)
    return False


async def _restore(hass: HomeAssistant, dev, entry_id: str) -> None:
    """Return the boiler to automatic. Idempotent, best-effort, loud on failure."""
    pump_ok = await _confirmed_write(dev, SOLAR_DUMP_FORCE_SLUG, 0, tries=6)
    mode_ok = await _confirmed_write(dev, OPERATING_MODE_SLUG, OPERATING_MODE_AUTO, tries=6)

    # Verify the mode actually came back, independent of the write ACK.
    read_back = None
    with contextlib.suppress(Exception):
        read_back = await dev.get_value(OPERATING_MODE_SLUG, retries=4)
    back_to_auto = read_back is not None and int(read_back) == OPERATING_MODE_AUTO

    if mode_ok and back_to_auto:
        _LOGGER.info("solar_to_buffer: boiler restored to automatic")
        clear_issue(hass, STUCK_ISSUE_ID)
    else:
        _LOGGER.error(
            "solar_to_buffer: FAILED to return the boiler to automatic "
            "(pump_cleared=%s mode_write=%s mode_read=%s) -- set the ecoSTER "
            "back to automatic manually",
            pump_ok,
            mode_ok,
            read_back,
        )
        raise_issue(hass, STUCK_ISSUE_ID, STUCK_ISSUE_ID, severity=ir.IssueSeverity.ERROR)


async def _dump_lifecycle(hass: HomeAssistant, coordinator, entry_id: str, hold_s: int) -> None:
    dev = coordinator.device
    touched = False
    try:
        mode = await dev.get_value(OPERATING_MODE_SLUG, retries=4)
        if mode is None or int(mode) != OPERATING_MODE_AUTO:
            _LOGGER.error(
                "solar_to_buffer: operating mode is %s, expected %d (automatic) -- "
                "not starting (is the boiler already in manual mode?)",
                mode,
                OPERATING_MODE_AUTO,
            )
            return

        touched = True
        if not await _confirmed_write(dev, OPERATING_MODE_SLUG, OPERATING_MODE_MANUAL):
            _LOGGER.error("solar_to_buffer: could not enter manual mode -- aborting")
            return

        await asyncio.sleep(3)
        state = await dev.get_value(MANUAL_MODE_SLUG, retries=4)
        if state is None or not (int(state) & MANUAL_MODE_BIT):
            _LOGGER.error(
                "solar_to_buffer: manual mode not confirmed by telemetry (%s=%s) -- aborting",
                MANUAL_MODE_SLUG,
                state,
            )
            return

        if not await _confirmed_write(dev, SOLAR_DUMP_FORCE_SLUG, SOLAR_DUMP_FORCE_VALUE):
            _LOGGER.error("solar_to_buffer: could not force the DHW pump -- aborting")
            return

        _LOGGER.info("solar_to_buffer: manual mode + DHW pump forced for %d min", hold_s // 60)
        await asyncio.sleep(hold_s)
        _LOGGER.info("solar_to_buffer: hold time elapsed")
    except asyncio.CancelledError:
        _LOGGER.info("solar_to_buffer: interrupted -- restoring")
        raise
    finally:
        _RUNNING.pop(entry_id, None)
        if touched:
            # Awaits inside a finally run to completion even while this task
            # is being cancelled (unload / HA stop / a replacing call), so
            # the return-to-automatic writes always go through. The caller
            # that cancelled us awaits this task, so it also waits for this.
            await _restore(hass, dev, entry_id)


async def _handle_solar_to_buffer(hass: HomeAssistant, call: ServiceCall) -> None:
    requested = int(call.data["duration"])
    hold_min = min(requested, SOLAR_DUMP_MAX_MINUTES)
    if hold_min != requested:
        _LOGGER.warning(
            "solar_to_buffer: duration %d min clamped to the %d min cap",
            requested,
            SOLAR_DUMP_MAX_MINUTES,
        )
    hold_s = hold_min * 60
    coordinators = dict(hass.data.get(DOMAIN, {}))
    if not coordinators:
        _LOGGER.warning("solar_to_buffer called but no Plum EcoMAX config entry is loaded")
        return

    for entry_id, coordinator in coordinators.items():
        existing = _RUNNING.get(entry_id)
        if existing and not existing.done():
            _LOGGER.info("solar_to_buffer: a run is active for %s -- restarting it", entry_id)
            existing.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await existing

        task = hass.async_create_task(
            _dump_lifecycle(hass, coordinator, entry_id, hold_s),
            name=f"{DOMAIN} solar_to_buffer {entry_id}",
        )
        _RUNNING[entry_id] = task


async def async_stop_for_entry(hass: HomeAssistant, entry_id: str) -> None:
    """Cancel a running dump for one entry and wait for its restore.

    Called from async_unload_entry BEFORE the device socket is closed, so
    the return-to-automatic writes still go through.
    """
    task = _RUNNING.get(entry_id)
    if task and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


async def _async_stop_all(hass: HomeAssistant) -> None:
    for entry_id in list(_RUNNING):
        await async_stop_for_entry(hass, entry_id)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register plum_ecomax.solar_to_buffer once (idempotent)."""
    global _STOP_UNSUB
    if not hass.services.has_service(DOMAIN, SERVICE_SOLAR_TO_BUFFER):

        async def _service(call: ServiceCall) -> None:
            await _handle_solar_to_buffer(hass, call)

        hass.services.async_register(
            DOMAIN, SERVICE_SOLAR_TO_BUFFER, _service, schema=SOLAR_TO_BUFFER_SCHEMA
        )

    if _STOP_UNSUB is None:

        async def _on_stop(_event) -> None:
            await _async_stop_all(hass)

        _STOP_UNSUB = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Drop the service when the last config entry unloads."""
    global _STOP_UNSUB
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SOLAR_TO_BUFFER)
        if _STOP_UNSUB is not None:
            _STOP_UNSUB()
            _STOP_UNSUB = None
