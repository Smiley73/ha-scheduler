"""Calendar platform for Scheduler integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .schedule_generator import generate_schedule_dates


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
        schedules_dict = self._entry.options.get("schedules", {})
        return list(schedules_dict.values())

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
        default_config = self._entry.options.get("configuration", {})
        current_year = today.year

        all_events = []
        for schedule in schedules:
            schedule_config = schedule.get("configuration", default_config)

            # Check current year and previous year (for year-wrapping schedules)
            for year in [current_year - 1, current_year, current_year + 1]:
                date_ranges = generate_schedule_dates(schedule, year)

                for schedule_start, schedule_end in date_ranges:
                    if schedule_start <= today <= schedule_end:
                        all_events.append(
                            (
                                schedule_start,
                                CalendarEvent(
                                    start=schedule_start,
                                    end=schedule_end + timedelta(days=1),
                                    summary=schedule["name"],
                                    uid=f"{schedule['uid']}_{year}",
                                    description=schedule_config,
                                ),
                            )
                        )

        if all_events:
            all_events.sort(key=lambda x: x[0])
            return all_events[0][1]

        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events = []
        schedules = self._get_schedules()
        default_config = self._entry.options.get("configuration", {})

        start_day = start_date.date()
        end_day = end_date.date()

        start_year = start_day.year
        end_year = end_day.year

        for schedule in schedules:
            schedule_config = schedule.get("configuration", default_config)

            # Include previous year to catch year-wrapping schedules
            for year in range(start_year - 1, end_year + 1):
                date_ranges = generate_schedule_dates(schedule, year)

                for schedule_start, schedule_end in date_ranges:
                    # Only include if it overlaps with requested range
                    if schedule_start <= end_day and schedule_end >= start_day:
                        events.append(
                            CalendarEvent(
                                start=schedule_start,
                                end=schedule_end + timedelta(days=1),
                                summary=schedule["name"],
                                uid=f"{schedule['uid']}_{year}",
                                description=schedule_config,
                            )
                        )

        return sorted(events, key=lambda x: x.start)
