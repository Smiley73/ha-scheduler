"""Calendar platform for Scheduler integration."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CALENDAR_YEAR_LOOKAROUND, DOMAIN
from .holiday_importer import async_prime_holiday_cache
from .schedule_generator import generate_schedule_dates

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Scheduler calendar from a config entry."""
    # Handle both new service-based structure and legacy structure
    services = entry.options.get("services", {})
    calendars = []
    all_schedules: list[dict[str, Any]] = []

    if services:
        # New service-based structure
        for service_id, service_data in services.items():
            all_schedules.extend(service_data.get("schedules", {}).values())
            calendars.append(SchedulerCalendar(entry, service_id, service_data))
    else:
        # Legacy structure - create a default service
        legacy_schedules = entry.options.get("schedules", {})
        legacy_config = entry.options.get("configuration", {})
        all_schedules.extend(legacy_schedules.values())

        default_service_data = {
            "name": entry.title,
            "schedules": legacy_schedules,
            "configuration": legacy_config,
        }
        calendars.append(SchedulerCalendar(entry, "default", default_service_data))

    current_year = dt_util.now().date().year
    await async_prime_holiday_cache(
        all_schedules,
        range(
            current_year - CALENDAR_YEAR_LOOKAROUND,
            current_year + CALENDAR_YEAR_LOOKAROUND + 1,
        ),
    )

    async_add_entities(calendars, True)


class SchedulerCalendar(CalendarEntity):
    """Representation of a Scheduler calendar."""

    _attr_has_entity_name = True
    _removed = False

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

        # With has_entity_name, a None name means the entity takes the device
        # name, preserving the historical "calendar.<scheduler title>" id for
        # single-service setups. Distinctly named services compose with the
        # device name ("<scheduler title> <service name>").
        self._attr_name = None if service_name == entry.title else service_name

        # Set device info to group calendars under the scheduler service
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="HA Scheduler",
            model="Scheduler Service",
        )

    async def async_added_to_hass(self) -> None:
        """Register update listener when entity is added to hass."""
        self.async_on_remove(
            self._entry.add_update_listener(self._async_update_listener)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Flag removal so in-flight update listeners stop early."""
        self._removed = True
        await super().async_will_remove_from_hass()

    async def _async_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        current_year = dt_util.now().date().year
        await async_prime_holiday_cache(
            self._get_schedules(),
            range(
                current_year - CALENDAR_YEAR_LOOKAROUND,
                current_year + CALENDAR_YEAR_LOOKAROUND + 1,
            ),
        )
        # The await above can outlive this entity: if the entity was removed
        # meanwhile, writing state would re-arm the calendar component's
        # event-transition timers with nothing left to cancel them.
        if self._removed:
            return
        self.async_write_ha_state()

    def _get_service_data(self) -> dict[str, Any]:
        """Return live service data, handling both new and legacy layouts."""
        services = self._entry.options.get("services", {})
        if services:
            return services.get(self._service_id, {})

        # Legacy (pre-services) entries store schedules at the options root.
        return {
            "name": self._entry.title,
            "schedules": self._entry.options.get("schedules", {}),
            "configuration": self._entry.options.get("configuration", {}),
        }

    def _get_schedules(self) -> list[dict[str, Any]]:
        """Get schedules from config entry options for this service."""
        schedules_dict = self._get_service_data().get("schedules", {})
        return [
            schedule if "uid" in schedule else {**schedule, "uid": schedule_id}
            for schedule_id, schedule in schedules_dict.items()
        ]

    def _get_current_or_upcoming_event(
        self,
    ) -> tuple[CalendarEvent, dict[str, Any]] | None:
        """Return the active event, or the next upcoming event when idle."""
        today = dt_util.now().date()
        current_year = today.year
        active_events: list[tuple[date, CalendarEvent, dict[str, Any]]] = []
        future_events: list[tuple[date, CalendarEvent, dict[str, Any]]] = []

        for schedule in self._get_schedules():
            try:
                # Check surrounding years to catch schedules that wrap across year boundaries
                for year in range(
                    current_year - CALENDAR_YEAR_LOOKAROUND,
                    current_year + CALENDAR_YEAR_LOOKAROUND + 1,
                ):
                    date_ranges = generate_schedule_dates(schedule, year)

                    for schedule_start, schedule_end in date_ranges:
                        # All-day events use date objects; CalendarEvent.end is
                        # exclusive, so add one day to include the end date.
                        event = CalendarEvent(
                            start=schedule_start,
                            end=schedule_end + timedelta(days=1),
                            summary=schedule["name"],
                            uid=f"{schedule['uid']}_{year}",
                            description="",
                        )
                        if schedule_start <= today <= schedule_end:
                            active_events.append((event.start, event, schedule))
                        elif schedule_start > today:
                            future_events.append((event.start, event, schedule))
            except Exception:  # noqa: BLE001 - one bad schedule must not hide the others
                _LOGGER.warning(
                    "Skipping schedule %r while determining the current event",
                    schedule.get("name", schedule.get("uid")),
                    exc_info=True,
                )

        candidates = active_events or future_events
        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        _, event, schedule = candidates[0]
        return (event, schedule)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        default_config = self._get_service_data().get("configuration", {})

        # Surface the schedule configuration for the active event, or the
        # next upcoming event when the calendar is currently idle.
        if next_event := self._get_current_or_upcoming_event():
            _, schedule = next_event
            schedule_config = schedule.get("configuration", default_config)
            return {
                "configuration": schedule_config,
                "name": schedule["name"],
                "schedule_uid": schedule["uid"],
                "default_configuration": default_config,
            }

        # No event available, return only the default configuration.
        return {
            "configuration": default_config,
            "name": None,
            "schedule_uid": None,
            "default_configuration": default_config,
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the active event, or the next upcoming event when idle."""
        if next_event := self._get_current_or_upcoming_event():
            event, _ = next_event
            return event

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

        await async_prime_holiday_cache(schedules, range(start_year - 1, end_year + 1))

        for schedule in schedules:
            try:
                # Include previous year to catch year-wrapping schedules
                for year in range(start_year - 1, end_year + 1):
                    date_ranges = generate_schedule_dates(schedule, year)

                    for schedule_start, schedule_end in date_ranges:
                        # Only include if it overlaps with requested range
                        if schedule_start <= end_day and schedule_end >= start_day:
                            # All-day events use date objects; CalendarEvent.end is
                            # exclusive, so add one day to include the end date.
                            events.append(
                                CalendarEvent(
                                    start=schedule_start,
                                    end=schedule_end + timedelta(days=1),
                                    summary=schedule["name"],
                                    uid=f"{schedule['uid']}_{year}",
                                    description="",
                                )
                            )
            except Exception:  # noqa: BLE001 - one bad schedule must not hide the others
                _LOGGER.warning(
                    "Skipping schedule %r while listing calendar events",
                    schedule.get("name", schedule.get("uid")),
                    exc_info=True,
                )

        return sorted(events, key=lambda x: x.start)
