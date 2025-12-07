"""Calendar platform for Scheduler integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Scheduler calendar from a config entry."""
    async_add_entities([SchedulerCalendar(entry)], True)


class SchedulerCalendar(CalendarEntity):
    """Representation of a Scheduler calendar."""

    _attr_has_entity_name = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the calendar."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        entry.async_on_unload(entry.add_update_listener(self._async_update_listener))

    async def _async_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        self.async_write_ha_state()

    def _get_schedules(self) -> list[dict[str, Any]]:
        """Get schedules from config entry options."""
        return self._entry.options.get("schedules", [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "default_configuration": self._entry.options.get("configuration", {}),
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        today = dt_util.now().date()
        schedules = self._get_schedules()

        for schedule in sorted(schedules, key=lambda x: x["start_date"]):
            start_date = date.fromisoformat(schedule["start_date"])
            end_date = date.fromisoformat(schedule["end_date"])

            if start_date <= today <= end_date:
                return CalendarEvent(
                    start=start_date,
                    end=end_date + timedelta(days=1),
                    summary=schedule["name"],
                    uid=schedule["uid"],
                )

        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events = []
        schedules = self._get_schedules()

        start_day = start_date.date()
        end_day = end_date.date()

        for schedule in schedules:
            schedule_start = date.fromisoformat(schedule["start_date"])
            schedule_end = date.fromisoformat(schedule["end_date"])

            # Check if schedule overlaps with requested range
            if schedule_start <= end_day and schedule_end >= start_day:
                events.append(
                    CalendarEvent(
                        start=schedule_start,
                        end=schedule_end + timedelta(days=1),
                        summary=schedule["name"],
                        uid=schedule["uid"],
                    )
                )

        return sorted(events, key=lambda x: x.start)
