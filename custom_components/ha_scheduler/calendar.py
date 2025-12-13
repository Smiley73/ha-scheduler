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
    # Handle both new service-based structure and legacy structure
    services = entry.options.get("services", {})
    calendars = []

    if services:
        # New service-based structure
        for service_id, service_data in services.items():
            calendars.append(SchedulerCalendar(entry, service_id, service_data))
    else:
        # Legacy structure - create a default service
        legacy_schedules = entry.options.get("schedules", {})
        legacy_config = entry.options.get("configuration", {})

        default_service_data = {
            "name": entry.title,
            "schedules": legacy_schedules,
            "configuration": legacy_config,
        }
        calendars.append(SchedulerCalendar(entry, "default", default_service_data))

    async_add_entities(calendars, True)


class SchedulerCalendar(CalendarEntity):
    """Representation of a Scheduler calendar."""

    _attr_has_entity_name = False

    def __init__(
        self, entry: ConfigEntry, service_id: str, service_data: dict[str, Any]
    ) -> None:
        """Initialize the calendar."""
        self._entry = entry
        self._service_id = service_id
        self._service_data = service_data

        # For single service (default), use the entry title as calendar name
        # For multiple services, use service name
        service_name = service_data.get("name", entry.title)

        # Maintain backward compatibility for unique ID
        # For the default service (migrated from v1), use just the entry_id
        # For additional services, use the full format
        if service_id == "default":
            self._attr_unique_id = entry.entry_id
        else:
            self._attr_unique_id = f"{entry.entry_id}_{service_id}"

        self._attr_name = service_name

        # Set device info to group calendars under the scheduler service
        self._attr_device_info = {
            "identifiers": {("ha_scheduler", entry.entry_id)},
            "name": entry.title,
            "manufacturer": "HA Scheduler",
            "model": "Scheduler Service",
        }

        entry.async_on_unload(entry.add_update_listener(self._async_update_listener))

    async def _async_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        self.async_write_ha_state()

    def _get_schedules(self) -> list[dict[str, Any]]:
        """Get schedules from config entry options for this service."""
        services = self._entry.options.get("services", {})
        service_data = services.get(self._service_id, {})
        schedules_dict = service_data.get("schedules", {})
        return list(schedules_dict.values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        services = self._entry.options.get("services", {})
        service_data = services.get(self._service_id, {})
        default_config = service_data.get("configuration", {})

        # Add current event configuration if available
        current_event = self.event
        if current_event:
            # Extract configuration from the current event
            schedules = self._get_schedules()

            # Find the schedule that matches the current event
            for schedule in schedules:
                if current_event.summary == schedule["name"]:
                    schedule_config = schedule.get("configuration", default_config)
                    return {
                        "configuration": schedule_config,
                        "name": schedule["name"],
                        "schedule_uid": schedule["uid"],
                        "default_configuration": default_config,
                    }

        # No active event, return default configuration
        return {
            "configuration": default_config,
            "name": None,
            "schedule_uid": None,
            "default_configuration": default_config,
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        today = dt_util.now().date()
        schedules = self._get_schedules()
        current_year = today.year

        all_events = []
        for schedule in schedules:
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
                                    description="",
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

        start_day = start_date.date()
        end_day = end_date.date()

        start_year = start_day.year
        end_year = end_day.year

        for schedule in schedules:
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
                                description="",
                            )
                        )

        return sorted(events, key=lambda x: x.start)
