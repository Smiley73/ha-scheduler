"""Calendar platform for Scheduler integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

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
                    # Create end datetime at 23:59:59 on the end date
                    end_datetime = datetime.combine(
                        schedule_end, datetime.max.time().replace(microsecond=0)
                    )
                    events.append(
                        CalendarEvent(
                            start=dt_util.start_of_local_day(
                                datetime.combine(schedule_start, datetime.min.time())
                            ),
                            end=dt_util.as_local(end_datetime),
                            summary=schedule_name,
                            description=f"Schedule: {schedule_name} ({schedule_type})",
                            uid=f"{schedule_id}_{schedule_start.isoformat()}",
                        )
                    )

            return events
        else:
            # For week-based schedules, generate events per year
            events = []
            start_year = start_date.year
            end_year = end_date.year

            for year in range(start_year, end_year + 1):
                # Calculate year boundaries within the requested range
                # Create timezone-aware boundaries if start_date is aware, otherwise naive
                if start_date.tzinfo is not None:
                    year_start_boundary = dt_util.start_of_local_day(
                        datetime(year, 1, 1)
                    )
                    year_end_boundary = dt_util.as_local(
                        datetime(year, 12, 31, 23, 59, 59)
                    )
                else:
                    year_start_boundary = datetime(year, 1, 1)
                    year_end_boundary = datetime(year, 12, 31, 23, 59, 59)

                year_start = max(start_date, year_start_boundary)
                year_end = min(end_date, year_end_boundary)

                year_events = self._generate_week_based_events(
                    schedule_id,
                    schedule_name,
                    schedule_data,
                    year_start,
                    year_end,
                    start_month,
                    end_month,
                )
                events.extend(year_events)

            return events

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
        """Generate events for week-based schedules."""
        # Calculate the actual start and end dates for the schedule period
        schedule_data.get("start_week", 0)
        schedule_data.get("end_week", 4)
        start_day_of_week = schedule_data.get("start_day_of_week", 0)
        end_day_of_week = schedule_data.get("end_day_of_week", 6)

        # Find the first and last dates matching the configured day-of-week
        current_date = start_date.date()
        end = end_date.date()

        first_start_dow_date = None  # First occurrence of start_day_of_week
        last_end_dow_date = None  # Last occurrence of end_day_of_week

        while current_date <= end:
            is_active = self._is_date_active(
                current_date, schedule_data, "week", start_month, end_month
            )

            if is_active:
                weekday = current_date.weekday()

                # Track first occurrence of start day of week
                if weekday == start_day_of_week and first_start_dow_date is None:
                    first_start_dow_date = current_date

                # Track last occurrence of end day of week
                if weekday == end_day_of_week:
                    last_end_dow_date = current_date

            current_date += timedelta(days=1)

        # Create a single event spanning from first start_dow to last end_dow
        if first_start_dow_date and last_end_dow_date:
            end_datetime = datetime.combine(
                last_end_dow_date, datetime.max.time().replace(microsecond=0)
            )
            return [
                CalendarEvent(
                    start=dt_util.start_of_local_day(
                        datetime.combine(first_start_dow_date, datetime.min.time())
                    ),
                    end=dt_util.as_local(end_datetime),
                    summary=schedule_name,
                    description=f"Schedule: {schedule_name} (week-based)",
                    uid=f"{schedule_id}_{first_start_dow_date.isoformat()}",
                )
            ]

        return []

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
        check_date.weekday()  # Monday=0, Sunday=6

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

            # Calculate the actual start and end dates for this month/year
            # The day-of-week selection determines the start/end dates,
            # but ALL days between those dates are active

            # Calculate start date: first start_day_of_week in start_week
            start_week_first_day = start_week * 7 + 1
            start_date_candidate = start_week_first_day

            # Find the first occurrence of start_day_of_week in the start week
            for day in range(start_week_first_day, min(start_week_first_day + 7, 32)):
                try:
                    test_date = datetime(check_date.year, current_month, day)
                    if test_date.weekday() == start_day_of_week:
                        start_date_candidate = day
                        break
                except ValueError:
                    break

            # Calculate end date: last occurrence of end_day_of_week in end_week
            end_week_first_day = end_week * 7 + 1
            end_date_candidate = end_week_first_day

            # Find the last occurrence of end_day_of_week in the end week
            for day in range(end_week_first_day, min(end_week_first_day + 7, 32)):
                try:
                    test_date = datetime(check_date.year, current_month, day)
                    if test_date.weekday() == end_day_of_week:
                        end_date_candidate = day
                except ValueError:
                    break

            # Check if current day is within the calculated range
            return start_date_candidate <= current_day <= end_date_candidate
