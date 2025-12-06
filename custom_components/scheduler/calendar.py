"""Calendar platform for Scheduler integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# No parallel update limits needed - all operations are local and read-only
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Scheduler calendar platform."""
    schedules = entry.data.get("schedules", {})

    # Create a single calendar entity for all schedules
    if schedules:
        calendar = SchedulerCalendar(hass, entry)
        async_add_entities([calendar])


class SchedulerCalendar(CalendarEntity):
    """Representation of a Scheduler calendar."""

    _attr_has_entity_name = True
    _attr_translation_key = "scheduler"
    _attr_name = None  # Use device name only

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the calendar."""
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_available = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "scheduler_hub")},
            "name": "Scheduler",
            "manufacturer": "Scheduler",
            "model": "Hub",
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        # Check if we have valid schedule data
        schedules = self._entry.data.get("schedules", {})
        if not schedules:
            self._attr_available = False
            return None

        self._attr_available = True
        events = self._get_events(datetime.now(), datetime.now() + timedelta(days=365))
        if events:
            return events[0]
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        # Check if we have valid schedule data
        schedules = self._entry.data.get("schedules", {})
        if not schedules:
            self._attr_available = False
            return []

        self._attr_available = True
        return self._get_events(start_date, end_date)

    def _get_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all calendar events for schedules within the date range."""
        schedules = self._entry.data.get("schedules", {})
        events = []

        for schedule_id, schedule_data in schedules.items():
            schedule_name = schedule_data.get("name", "Schedule")
            schedule_type = schedule_data.get("schedule_type", "date")

            # Generate events for this schedule
            schedule_events = self._generate_schedule_events(
                schedule_id,
                schedule_name,
                schedule_data,
                schedule_type,
                start_date,
                end_date,
            )
            events.extend(schedule_events)

        # Sort events by start time
        events.sort(key=lambda e: e.start)
        return events

    def _generate_schedule_events(
        self,
        schedule_id: str,
        schedule_name: str,
        schedule_data: dict,
        schedule_type: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Generate calendar events for a single schedule."""
        start_month = schedule_data.get("start_month", 1)
        end_month = schedule_data.get("end_month", 12)

        if schedule_type == "date":
            start_day = schedule_data.get("start_day", 1)
            end_day = schedule_data.get("end_day", 31)

            # Generate events for each year in the requested range
            events = []
            start_year = start_date.year
            end_year = end_date.year

            for year in range(start_year, end_year + 1):
                schedule_start, schedule_end = self._calculate_schedule_dates_for_year(
                    year,
                    start_month,
                    end_month,
                    start_day,
                    end_day,
                    start_date,
                    end_date,
                )

                if schedule_start and schedule_end:
                    events.append(
                        CalendarEvent(
                            start=schedule_start,
                            end=schedule_end + timedelta(days=1),  # End is exclusive
                            summary=schedule_name,
                            description=f"Schedule: {schedule_name} ({schedule_type})",
                            uid=f"{schedule_id}_{schedule_start.isoformat()}",
                        )
                    )

            return events
        else:
            # For week-based schedules, still generate individual events
            # as they may not be continuous
            return self._generate_week_based_events(
                schedule_id,
                schedule_name,
                schedule_data,
                start_date,
                end_date,
                start_month,
                end_month,
            )

        return []

    def _calculate_schedule_dates_for_year(
        self,
        year: int,
        start_month: int,
        end_month: int,
        start_day: int,
        end_day: int,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[datetime.date | None, datetime.date | None]:
        """Calculate the actual start and end dates for a date-based schedule in a specific year."""
        # Handle wrap-around schedules (e.g., Nov-Feb)
        if start_month > end_month:
            # Schedule wraps around year boundary
            schedule_start = self._get_valid_date(year, start_month, start_day)
            schedule_end = self._get_valid_date(year + 1, end_month, end_day)
        else:
            # Normal schedule within same year
            schedule_start = self._get_valid_date(year, start_month, start_day)
            schedule_end = self._get_valid_date(year, end_month, end_day)

        # If either date is invalid, skip this schedule instance
        if schedule_start is None or schedule_end is None:
            return None, None

        # Ensure the schedule overlaps with the requested range
        if schedule_end < range_start.date() or schedule_start > range_end.date():
            return None, None

        return schedule_start, schedule_end

    def _get_valid_date(self, year: int, month: int, day: int) -> datetime.date | None:
        """Get a valid date, adjusting for invalid dates like Feb 29 in non-leap years."""
        try:
            return datetime(year, month, day).date()
        except ValueError:
            # Invalid date - try to find the last valid day of the month
            # This handles cases like Feb 29-31 in non-leap years
            import calendar

            last_day = calendar.monthrange(year, month)[1]
            if day > last_day:
                # Use the last valid day of the month
                try:
                    return datetime(year, month, last_day).date()
                except ValueError:
                    return None
            return None

    def _generate_week_based_events(
        self,
        schedule_id: str,
        schedule_name: str,
        schedule_data: dict,
        start_date: datetime,
        end_date: datetime,
        start_month: int,
        end_month: int,
    ) -> list[CalendarEvent]:
        """Generate individual events for week-based schedules."""
        events = []
        current_date = start_date.date()
        end = end_date.date()

        while current_date <= end:
            if self._is_date_active(
                current_date, schedule_data, "week", start_month, end_month
            ):
                event = CalendarEvent(
                    start=current_date,
                    end=current_date + timedelta(days=1),
                    summary=schedule_name,
                    description=f"Schedule: {schedule_name} (week-based)",
                    uid=f"{schedule_id}_{current_date.isoformat()}",
                )
                events.append(event)

            current_date += timedelta(days=1)

        return events

    def _is_date_active(
        self,
        check_date: datetime.date,
        schedule_data: dict,
        schedule_type: str,
        start_month: int,
        end_month: int,
    ) -> bool:
        """Check if a specific date is active for the schedule."""
        current_month = check_date.month
        current_day = check_date.day
        current_weekday = check_date.weekday()  # Monday=0, Sunday=6

        # Check if current month is in range
        if start_month <= end_month:
            # Normal range (e.g., January to December)
            if not (start_month <= current_month <= end_month):
                return False
        else:
            # Wrap-around range (e.g., November to February)
            if not (current_month >= start_month or current_month <= end_month):
                return False

        if schedule_type == "date":
            # Date-based schedule
            start_day = schedule_data.get("start_day", 1)
            end_day = schedule_data.get("end_day", 31)

            # If we're in the start month, check if we're past the start day
            if current_month == start_month and current_day < start_day:
                return False

            # If we're in the end month, check if we're before the end day
            if current_month == end_month and current_day > end_day:
                return False

            return True

        else:  # week-based schedule
            start_day_of_week = schedule_data.get("start_day_of_week", 0)
            end_day_of_week = schedule_data.get("end_day_of_week", 6)
            start_week = schedule_data.get("start_week", 0)
            end_week = schedule_data.get("end_week", 4)

            # Calculate which week of the month we're in (0-4)
            week_of_month = (current_day - 1) // 7

            # Check if current week is in range
            if not (start_week <= week_of_month <= end_week):
                return False

            # Check if current day of week is in range
            if start_day_of_week <= end_day_of_week:
                # Normal range (e.g., Monday to Friday)
                if not (start_day_of_week <= current_weekday <= end_day_of_week):
                    return False
            else:
                # Wrap-around range (e.g., Friday to Monday)
                if not (
                    current_weekday >= start_day_of_week
                    or current_weekday <= end_day_of_week
                ):
                    return False

            return True
