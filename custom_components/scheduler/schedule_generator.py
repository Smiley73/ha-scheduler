"""Schedule generator for different schedule types."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any


def generate_schedule_dates(
    schedule: dict[str, Any], year: int
) -> list[tuple[date, date]]:
    """Generate date ranges for a schedule in a given year.

    For by-week and by-nth-day schedules, the actual calendar dates will vary
    each year. For example:
    - "First Monday of January" is Jan 1, 2024 but Jan 6, 2025
    - "Last Friday of December" is Dec 29, 2023 but Dec 27, 2024

    This function recalculates the actual dates for the specified year.
    """
    schedule_type = schedule.get("schedule_type", "date")

    if schedule_type == "date":
        return _generate_by_date(schedule, year)
    if schedule_type == "week":
        return _generate_by_week(schedule, year)
    if schedule_type == "nth-day":
        return _generate_by_nth_day(schedule, year)

    return []


def _generate_by_date(schedule: dict[str, Any], year: int) -> list[tuple[date, date]]:
    """Generate dates for 'by_date' schedule type.

    Handles year wrapping (e.g., Dec 15 to Jan 15).
    """
    start_month = schedule["start_month"]
    start_day = schedule["start_day"]
    end_month = schedule["end_month"]
    end_day = schedule["end_day"]

    try:
        # Validate and clamp days to valid range for the month
        max_start_day = calendar.monthrange(year, start_month)[1]
        actual_start_day = min(start_day, max_start_day)

        start_date = date(year, start_month, actual_start_day)

        # Check if schedule wraps to next year
        if end_month < start_month or (
            end_month == start_month and end_day < start_day
        ):
            # Schedule wraps to next year
            max_end_day = calendar.monthrange(year + 1, end_month)[1]
            actual_end_day = min(end_day, max_end_day)
            end_date = date(year + 1, end_month, actual_end_day)
        else:
            # Schedule stays within the same year
            max_end_day = calendar.monthrange(year, end_month)[1]
            actual_end_day = min(end_day, max_end_day)
            end_date = date(year, end_month, actual_end_day)

        return [(start_date, end_date)]
    except (ValueError, KeyError):
        return []


def _generate_by_week(schedule: dict[str, Any], year: int) -> list[tuple[date, date]]:
    """Generate dates for 'by_week' schedule type.

    Handles year wrapping only when end_month < start_month
    (e.g., last Monday of December to first Friday of January).
    """
    start_month = schedule["start_month"]
    start_week = schedule["start_week"]
    start_day_of_week = schedule["start_day_of_week"]
    end_month = schedule["end_month"]
    end_week = schedule["end_week"]
    end_day_of_week = schedule["end_day_of_week"]

    try:
        start_date = _get_nth_weekday(year, start_month, start_week, start_day_of_week)

        if not start_date:
            return []

        # Only wrap to next year if end month is explicitly before start month
        if end_month < start_month:
            # End is in next year (e.g., December to January)
            end_date = _get_nth_weekday(year + 1, end_month, end_week, end_day_of_week)
        else:
            # Same year - end month is same or after start month
            end_date = _get_nth_weekday(year, end_month, end_week, end_day_of_week)

        if not end_date:
            return []

        return [(start_date, end_date)]
    except (ValueError, KeyError):
        return []


def _generate_by_nth_day(
    schedule: dict[str, Any], year: int
) -> list[tuple[date, date]]:
    """Generate dates for 'by_nth_day' schedule type.

    The target date is recalculated each year based on the occurrence.
    For example, "Second Tuesday of March" will be:
    - March 14, 2023
    - March 12, 2024
    - March 11, 2025
    """
    month = schedule["month"]
    occurrence = schedule["occurrence"]
    day_of_week = schedule["day_of_week"]
    start_offset = schedule.get("start_offset", 0)
    end_offset = schedule.get("end_offset", 0)

    try:
        target_date = _get_nth_weekday(year, month, occurrence, day_of_week)

        if not target_date:
            return []

        start_date = target_date - timedelta(days=start_offset)
        end_date = target_date + timedelta(days=end_offset)

        return [(start_date, end_date)]
    except (ValueError, KeyError):
        return []


def _get_nth_weekday(
    year: int, month: int, occurrence: int, day_of_week: int
) -> date | None:
    """Get the nth occurrence of a weekday in a month.

    occurrence: 0-3 for first through fourth, 4 for last
    day_of_week: 0-6 for Monday through Sunday
    """
    try:
        # Get first day of month
        first_day = date(year, month, 1)

        # Handle "last" occurrence
        if occurrence == 4:
            # Start from last day of month and work backwards
            last_day = calendar.monthrange(year, month)[1]
            for day in range(last_day, 0, -1):
                check_date = date(year, month, day)
                if check_date.weekday() == day_of_week:
                    return check_date
            return None

        # Find first occurrence of the weekday
        days_until_target = (day_of_week - first_day.weekday()) % 7
        first_occurrence = first_day + timedelta(days=days_until_target)

        # Add weeks for nth occurrence
        target_date = first_occurrence + timedelta(weeks=occurrence)

        # Verify it's still in the same month
        if target_date.month != month:
            return None

        return target_date
    except (ValueError, OverflowError):
        return None


def check_overlap(
    schedule: dict[str, Any],
    existing_schedules: list[dict[str, Any]],
    exclude_uid: str | None = None,
) -> tuple[bool, str | None]:
    """Check if a schedule overlaps with existing schedules.

    Note: For by-week and by-nth-day schedules, the actual dates vary each year
    (e.g., "first Monday of January" is different in 2024 vs 2025).
    We check multiple years to ensure no overlaps occur in any year.

    Returns:
        Tuple of (has_overlap, conflicting_schedule_name)
    """
    # Validate schedule has required fields
    if "schedule_type" not in schedule:
        return (False, None)

    current_year = date.today().year
    new_dates = []

    # Check multiple years to catch varying date patterns
    # For by-week/by-nth-day, dates shift each year
    for year in range(current_year, current_year + 3):
        new_dates.extend(generate_schedule_dates(schedule, year))

    if not new_dates:
        return (False, None)

    # Check against existing schedules
    for existing in existing_schedules:
        if exclude_uid and existing.get("uid") == exclude_uid:
            continue

        existing_dates = []
        for year in range(current_year, current_year + 3):
            existing_dates.extend(generate_schedule_dates(existing, year))

        # Check for overlaps across all generated date ranges
        for new_start, new_end in new_dates:
            for exist_start, exist_end in existing_dates:
                if new_start <= exist_end and new_end >= exist_start:
                    return (True, existing.get("name", "Unknown"))

    return (False, None)
