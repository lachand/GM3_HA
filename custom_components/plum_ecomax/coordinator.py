"""Data Update Coordinator for Plum EcoMAX.

This module provides the central data management logic for the integration.
It handles polling, caching, validation, and a robust "fire-and-forget"
write strategy to ensure commands reach the device despite network latency.
"""
import logging
import asyncio
import time
from datetime import timedelta
from typing import Any, Dict, Tuple, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# Conditional import for typing only
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .plum_device import PlumDevice

from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    SENSOR_TYPES,
    CLIMATE_TYPES,
    NUMBER_TYPES,
    SCHEDULE_TYPES,
    WATER_HEATER_TYPES,
    SWITCH_TYPES,
    SELECT_TYPES,
    DEVICE_INFO_PARAMS,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TTL = 300

# Definitions of physical limits for validation
VALIDATION_RANGES = {
    "temp": (-20, 100.0),
    "power": (0, 100),
    "fan": (0, 100),
    "valveposition": (0, 100),
    "pressure": (0.0, 4.0),
    "lambda": (0.0, 25.0),
}

class PlumDataUpdateCoordinator(DataUpdateCoordinator):
    """Centralized data management with Robust Data Validation.

    Implements caching, write-through strategies, and data sanitization
    to prevent outliers from polluting the state machine.
    """

    def __init__(self, hass: HomeAssistant, device: "PlumDevice"):
        """Initializes the coordinator.

        Args:
            hass: Home Assistant core instance.
            device: The low-level PlumDevice instance.
        """
        self.device = device
        self.available_slugs: list[str] = []
        
        # Cache System
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._cache_lock = asyncio.Lock()
        self.ttl = DEFAULT_TTL

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Main update loop with Validation and Fallback.

        Returns:
            dict: The validated data.
        """
        data = {}
        now = time.time()

        if not self.available_slugs:
            await self._detect_available_parameters()

        # 1. Split into cache hits vs. slugs that need a fresh read
        to_fetch = []
        for slug in self.available_slugs:
            async with self._cache_lock:
                last_update = self._timestamps.get(slug, 0)
                is_fresh = (now - last_update) < self.ttl
                cached_val = self._cache.get(slug)

            if is_fresh and cached_val is not None:
                data[slug] = cached_val
            else:
                to_fetch.append(slug)

        # 2. Batch-fetch everything stale in as few frames as possible
        # (spec 1.5.3.12 allows several parameter blocks per request), instead
        # of one TCP connection per parameter.
        raw_values: Dict[str, Any] = {}
        if to_fetch:
            try:
                raw_values = await self.device.get_values(to_fetch, retries=2)
            except Exception as e:
                _LOGGER.warning("Error during batched read of %d parameters: %s", len(to_fetch), e)

        # 3. Validate & fall back per-slug
        for slug in to_fetch:
            async with self._cache_lock:
                cached_val = self._cache.get(slug)

            raw_val = raw_values.get(slug)
            is_valid, final_val = self._validate_value(slug, raw_val, cached_val)

            if is_valid:
                # Valid new data: Update cache
                async with self._cache_lock:
                    self._cache[slug] = final_val
                    self._timestamps[slug] = time.time()
                data[slug] = final_val
            else:
                # Invalid data: Use fallback (Hold Last State)
                if cached_val is not None:
                    data[slug] = cached_val

        return data

    def _validate_value(self, slug: str, raw_val: Any, cached_val: Any) -> Tuple[bool, Any]:
        """Sanitizes the raw value based on JSON limits or Generic constraints.

        Args:
            slug: The parameter identifier.
            raw_val: The raw value received.
            cached_val: The previous value (for delta checking).

        Returns:
            Tuple[bool, Any]: (IsValid, SafeValue).
        """
        # A. Basic protocol checks
        if raw_val is None:
            return False, None
            
        if isinstance(raw_val, (int, float)):
            if raw_val == 999.0 or raw_val == 999:
                _LOGGER.debug("Rejection: %s returned sensor error code %s", slug, raw_val)
                return False, None
                
        param_def = self.device.params_map.get(slug, {})
        json_min = param_def.get("min")
        json_max = param_def.get("max")
        json_max_delta = param_def.get("max_delta")

        # B. Specific bounds check (JSON)
        if (json_min is not None or json_max is not None) and isinstance(raw_val, (int, float)):
            is_valid = True
            
            if json_min is not None and raw_val < json_min:
                is_valid = False
            if json_max is not None and raw_val > json_max:
                is_valid = False
            # Fix typo from original code: is_valide -> is_valid
            if json_max_delta is not None and cached_val is not None and abs(cached_val - raw_val) > json_max_delta:
                is_valid = False
                
            if not is_valid:
                return False, None
        
            return True, raw_val

        # C. Generic bounds check (Fallback)
        if isinstance(raw_val, (int, float)):
            for keyword, (min_v, max_v) in VALIDATION_RANGES.items():
                if keyword in slug:
                    if not (min_v <= raw_val <= max_v):
                        return False, None
                    break 
                    
        return True, raw_val
        

    async def async_set_value(self, slug: str, value: Any) -> bool:
        """Writes a value using Optimistic UI + Repeated Background Sends.

        1. Updates the internal cache immediately so the UI is responsive.
        2. Launches a background task to send the command (up to 5 attempts)
           and reconcile the optimistic cache with what the device actually
           confirmed once it answers.

        Args:
            slug: The parameter identifier.
            value: The value to write.

        Returns:
            bool: Always True (Optimistic). Use the entity's later state
            (or the logs) to learn whether the device actually confirmed it.
        """
        # 1. Optimistic Cache Update (Immediate)
        async with self._cache_lock:
            previous_val = self._cache.get(slug)
            self._cache[slug] = value
            self._timestamps[slug] = time.time()

        # Notify Home Assistant immediately
        self.async_set_updated_data(self._cache)
        _LOGGER.info("Optimistic set for %s=%s. Launching background sends.", slug, value)

        # 2. Launch background task for repeated sending
        # This prevents blocking the UI or the event loop
        asyncio.create_task(self._perform_repeated_write(slug, value, previous_val))

        return True

    async def _perform_repeated_write(self, slug: str, value: Any, previous_val: Any = None) -> None:
        """Background task to send the write command and reconcile state.

        Sends the command up to 5 times, 2 seconds apart, stopping as soon
        as `device.set_value()` reports a confirmed write (the boiler's own
        0xE5 result code, validated in plum_device._sync_set_value -- not
        just "a response arrived"). If none of the 5 attempts are
        confirmed, the optimistic cache entry is reverted so the UI doesn't
        keep showing a value the boiler never actually applied. Either way,
        the slug's cache entry is marked stale so the next poll cycle
        re-reads the real hardware state instead of trusting the optimistic
        value for the full cache TTL.

        Args:
            slug: Parameter slug.
            value: Value to write.
            previous_val: The cached value before this optimistic write, to
                restore if the device never confirms.
        """
        confirmed = False
        for i in range(1, 6):  # up to 5 attempts
            _LOGGER.debug("Sending %s=%s (attempt %d/5)", slug, value, i)
            if await self.device.set_value(slug, value):
                confirmed = True
                break

            # Wait 2 seconds between sends, but not after the last one
            if i < 5:
                await asyncio.sleep(2.0)

        async with self._cache_lock:
            if confirmed:
                # Force a real read at the next poll instead of trusting the
                # optimistic value for the full cache TTL.
                self._timestamps[slug] = 0
            else:
                _LOGGER.warning(
                    "Write %s=%s was never confirmed by the device after 5 attempts; "
                    "reverting optimistic state to %s.",
                    slug, value, previous_val,
                )
                if previous_val is not None:
                    self._cache[slug] = previous_val
                else:
                    self._cache.pop(slug, None)
                self._timestamps[slug] = 0

        self.async_set_updated_data(self._cache)

    async def _detect_available_parameters(self) -> None:
        """Initial scan to filter out unsupported parameters."""
        _LOGGER.info("Initial scan of available parameters...")

        targets = []
        targets.extend(list(SENSOR_TYPES.keys()))
        for conf in CLIMATE_TYPES.values(): targets.extend(conf)
        targets.extend(list(NUMBER_TYPES.keys()))
        for conf in WATER_HEATER_TYPES.values(): targets.extend(conf)
        # Added Schedule types to detection
        targets.extend(list(SCHEDULE_TYPES.keys()))
        # SWITCH_TYPES/SELECT_TYPES were missing here entirely: since
        # _async_update_data() only ever polls self.available_slugs, any
        # switch/select slug not detected here was never re-read after the
        # initial optimistic write, so its state reverted to unknown at the
        # very next poll cycle regardless of the real hardware state.
        targets.extend(list(SWITCH_TYPES.keys()))
        targets.extend(list(SELECT_TYPES.keys()))
        # Not an entity, but device_info properties read this from
        # coordinator.data (see const.py's DEVICE_INFO_PARAMS docstring).
        targets.extend(DEVICE_INFO_PARAMS)

        # Dedupe while preserving order, then read everything in as few
        # batched frames as possible instead of one connection per slug.
        candidates = [slug for slug in dict.fromkeys(targets) if slug in self.device.params_map]
        values = await self.device.get_values(candidates, retries=5)

        # Filter invalid values (999.0 often indicates a disconnected probe)
        valid_slugs = [slug for slug, val in values.items() if val is not None and val != 999.0]

        self.available_slugs = list(set(valid_slugs))
        _LOGGER.info("%d active parameters retained.", len(self.available_slugs))