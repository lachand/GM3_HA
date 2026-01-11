import logging
import asyncio
import time
from datetime import timedelta
from typing import Any, Dict, Optional
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, UPDATE_INTERVAL, SENSOR_TYPES, CLIMATE_TYPES, NUMBER_TYPES

_LOGGER = logging.getLogger(__name__)

## Default cache validity duration in seconds (should be slightly lower than UPDATE_INTERVAL)
DEFAULT_TTL = 25

class PlumDataUpdateCoordinator(DataUpdateCoordinator):
    """
    @class PlumDataUpdateCoordinator
    @brief Centralized data management for Plum ecoNET devices.
    @details Handles periodic polling, parameter discovery, and data caching.
    Acts as a middleware between Home Assistant entities and the physical device.
    """

    def __init__(self, hass, device):
        """
        @brief Constructor.
        @param hass Home Assistant core instance.
        @param device The low-level PlumDevice instance.
        """
        self.device = device
        self.available_slugs = [] ##< List of validated parameter slugs.
        
        # --- Cache System ---
        self._cache: Dict[str, Any] = {}       ##< Stores the latest known values.
        self._timestamps: Dict[str, float] = {} ##< Stores the time of the last successful fetch.
        self._cache_lock = asyncio.Lock()      ##< Ensures thread-safety during reads/writes.
        self.ttl = DEFAULT_TTL                 ##< Time To Live for cache entries.

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self):
        """
        @brief Main update loop triggered by Home Assistant every 30 seconds.
        @details Iterates through discovered parameters. Uses cached data if it is
        fresh enough (valid TTL), otherwise fetches from the device.
        
        @return Dict[str, Any] The complete dataset for all sensors.
        """
        data = {}
        now = time.time()
        
        # 1. Discovery phase (runs only once)
        if not self.available_slugs:
            await self._detect_available_parameters()

        # 2. Data collection loop
        for slug in self.available_slugs:
            async with self._cache_lock:
                last_update = self._timestamps.get(slug, 0)
                is_fresh = (now - last_update) < self.ttl
                cached_val = self._cache.get(slug)

            # A. Cache Hit: Data is fresh, skip network request
            if is_fresh and cached_val is not None:
                data[slug] = cached_val
                continue

            # B. Cache Miss: Fetch from device
            try:
                # We release the lock during the network call to allow other tasks to run
                val = await self.device.get_value(slug, retries=2)
                
                if val is not None:
                    async with self._cache_lock:
                        self._cache[slug] = val
                        self._timestamps[slug] = time.time()
                    data[slug] = val
                else:
                    # Fallback: Use old cache if fetch fails, but log it
                    if cached_val is not None:
                        data[slug] = cached_val
                        _LOGGER.debug(f"Fetch failed for {slug}, using stale cache.")

            except Exception as e:
                _LOGGER.warning(f"Error reading {slug}: {e}")
                # Persistence: keep existing data on error if possible
                if slug in self._cache:
                    data[slug] = self._cache[slug]
        
        return data

    async def async_set_value(self, slug: str, value: Any) -> bool:
        """
        @brief Writes a value to the device and updates the local cache immediately.
        @details This implements the 'Write-Through' pattern. It allows the UI to 
        update instantly without waiting for the next poll interval (Optimistic UI).
        
        @param slug The parameter identifier.
        @param value The value to write.
        @return bool True if the write was successful.
        """
        # 1. Perform the physical write
        success = await self.device.set_value(slug, value)
        
        if success:
            # 2. Update cache immediately (Optimistic update)
            async with self._cache_lock:
                self._cache[slug] = value
                self._timestamps[slug] = time.time()
            
            # 3. Notify Home Assistant that data has changed
            # This forces entities to refresh their state from our cache
            self.async_set_updated_data(self._cache)
            _LOGGER.info(f"✅ Value {slug}={value} set and cache updated.")
        else:
            _LOGGER.error(f"❌ Failed to set {slug}={value}")
            
        return success

    async def _detect_available_parameters(self):
        """
        @brief Initial scan to filter out unsupported parameters.
        @details Checks existence in JSON map and attempts a physical read.
        """
        _LOGGER.info("🔍 Initial scan of available parameters...")
        
        targets = []
        
        # 1. Sensors
        targets.extend(list(SENSOR_TYPES.keys()))
        
        # 2. Climates (Temperature + Target)
        for conf in CLIMATE_TYPES.values():
            targets.extend(conf) 
            
        # 3. Numbers
        targets.extend(list(NUMBER_TYPES.keys()))
        
        valid_slugs = []
        for slug in targets:
            if slug not in self.device.params_map:
                continue
                
            val = await self.device.get_value(slug, retries=2)
            
            # Filter invalid values (999.0 often indicates a disconnected probe)
            if val is not None and val != 999.0:
                 valid_slugs.append(slug)
                 _LOGGER.debug(f"Detected parameter: {slug}")
        
        self.available_slugs = list(set(valid_slugs))
        _LOGGER.info(f"✅ {len(self.available_slugs)} active parameters retained.")
