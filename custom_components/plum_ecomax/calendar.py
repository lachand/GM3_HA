import logging
import datetime
from typing import Any, List, Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, WEEKDAY_TO_SLUGS, CONF_ACTIVE_CIRCUITS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up Calendar entities for Circuits and DHW.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry containing the configuration.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected_circuits = entry.data.get(CONF_ACTIVE_CIRCUITS, [])
    entities = []

    # 1. Circuit's calendar
    for circuit_id in selected_circuits:
        if f"circuit{circuit_id}mondayam" in coordinator.device.params_map:
            entities.append(PlumEconetCalendar(coordinator, entry, "circuit", circuit_id))

    # 2. HDW's calendar
    if "hdwmondayam" in coordinator.device.params_map:
        entities.append(PlumEconetCalendar(coordinator, entry, "hdw", 0))

    async_add_entities(entities)


class PlumEconetCalendar(CoordinatorEntity, CalendarEntity):
    """Representation of a Plum EcoMAX Calendar.

    This entity reads binary registers (AM/PM bitmasks) and converts them
    into readable Home Assistant Calendar events. It supports both
    heating circuits and domestic hot water (DHW).
    """

    def __init__(self, coordinator, entry, system_type: str, index: int):
        """Initializes the calendar entity.

        Args:
            coordinator: The data update coordinator.
            entry: The config entry.
            system_type: The type of system ('circuit' or 'hdw').
            index: The circuit index (1-7) or 0 for HDW.
        """
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._system_type = system_type  # 'circuit' or 'hdw'
        self._index = index
        self._event = None

        if self._system_type == "circuit":
            self._attr_name = f"Calendar Circuit {index}"
            self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_calendar_circuit_{index}"
        else:
            self._attr_name = "DHW Calendar"
            self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_calendar_hdw"

    @property
    def event(self) -> CalendarEvent | None:
        """Returns the next upcoming event.

        Returns:
            CalendarEvent: The next event, or None if not implemented.
        """
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime.datetime, end_date: datetime.datetime
    ) -> List[CalendarEvent]:
        """Generates events based on the system type.

        Args:
            hass: Home Assistant instance.
            start_date: Start of the requested date range.
            end_date: End of the requested date range.

        Returns:
            List[CalendarEvent]: A list of calendar events found within the range.
        """
        events = []
        current_day = start_date
        
        while current_day <= end_date:
            weekday = current_day.weekday()
            slugs = WEEKDAY_TO_SLUGS.get(weekday)
            
            if not slugs: 
                current_day += datetime.timedelta(days=1)
                continue

            suffix_am, suffix_pm = slugs
            
            if self._system_type == "circuit":
                slug_am = f"circuit{self._index}{suffix_am}"
                slug_pm = f"circuit{self._index}{suffix_pm}"
            else:
                slug_am = f"hdw{suffix_am}"
                slug_pm = f"hdw{suffix_pm}"
            
            val_am = self.coordinator.data.get(slug_am)
            val_pm = self.coordinator.data.get(slug_pm)
            
            if val_am is not None and val_pm is not None:
                try:
                    day_events = self._decode_day(current_day, int(val_am), int(val_pm))
                    events.extend(day_events)
                except (ValueError, TypeError):
                    pass

            current_day += datetime.timedelta(days=1)
            
        return events

    def _decode_day(self, date_base: datetime.datetime, val_am: int, val_pm: int) -> List[CalendarEvent]:
        """Decodes 48-bit binary schedule data for a single day.

        Args:
            date_base: The base date (00:00).
            val_am: Integer value of the AM register (00:00-12:00).
            val_pm: Integer value of the PM register (12:00-00:00).

        Returns:
            List[CalendarEvent]: List of events derived from the bitmask.
        """
        events = []
        slots = []
        for i in range(24): slots.append((val_am >> i) & 1 == 1)
        for i in range(24): slots.append((val_pm >> i) & 1 == 1)
        
        if not slots: return []

        current_start_slot = 0
        current_state = slots[0]

        for i in range(1, 48):
            state = slots[i]
            if state != current_state:
                events.append(self._create_event(date_base, current_start_slot, i, current_state))
                current_state = state
                current_start_slot = i
        
        events.append(self._create_event(date_base, current_start_slot, 48, current_state))
        return events

    def _create_event(self, date_base, start_slot, end_slot, is_active) -> CalendarEvent:
        """Creates a Home Assistant CalendarEvent object.

        Args:
            date_base: The reference date.
            start_slot: Start index (0-47, representing 30min slots).
            end_slot: End index (0-48).
            is_active: Boolean indicating if the slot is Active (Comfort) or Eco.

        Returns:
            CalendarEvent: The constructed event object.
        """
        start_h = start_slot // 2
        start_m = (start_slot % 2) * 30
        end_h = end_slot // 2
        end_m = (end_slot % 2) * 30
        
        dt_start = dt_util.as_local(date_base.replace(hour=int(start_h), minute=int(start_m), second=0, microsecond=0))
        
        if end_h >= 24:
            dt_end = dt_util.as_local(date_base.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1))
        else:
            dt_end = dt_util.as_local(date_base.replace(hour=int(end_h), minute=int(end_m), second=0, microsecond=0))

        if is_active:
            summary = "Active"
            description = "Heating/DHW comfort (Day)"
        else:
            summary = "Eco"
            description = "Heating/DHW eco (Night)"

        return CalendarEvent(
            summary=summary,
            start=dt_start,
            end=dt_end,
            description=description
        )
    
    @property
    def device_info(self) -> DeviceInfo:
        """Links the calendar to the correct device registry entry.

        Returns:
            DeviceInfo: Configuration to link this entity to a circuit or HDW device.
        """
        if self._system_type == "circuit":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self._entry_id}_circuit_{self._index}")},
                name=f"Circuit {self._index}",
                manufacturer="Plum",
                via_device=(DOMAIN, self._entry_id),
            )
        else:
            return DeviceInfo(
                identifiers={(DOMAIN, "plum_hdw")},
                name="HDW",
                manufacturer="Plum",
                model="HDW Monitor",
                via_device=(DOMAIN, self._entry_id),
            )