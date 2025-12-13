"""Schedule generator for different schedule types."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

# Country-specific first weekday mapping (ISO 3166-1 alpha-2 codes)
# 0 = Monday, 6 = Sunday
COUNTRY_FIRST_WEEKDAY = {
    # Sunday-first countries
    "US": 6,
    "CA": 6,
    "MX": 6,
    "BR": 6,
    "JP": 6,
    "KR": 6,
    "IL": 6,
    "SA": 6,
    "AE": 6,
    "EG": 6,
    "JO": 6,
    "LB": 6,
    "SY": 6,
    "IQ": 6,
    "KW": 6,
    "QA": 6,
    "BH": 6,
    "OM": 6,
    "YE": 6,
    "AF": 6,
    "PK": 6,
    "BD": 6,
    "NP": 6,
    "LK": 6,
    "MV": 6,
    "MM": 6,
    "TH": 6,
    "LA": 6,
    "KH": 6,
    "VN": 6,
    "PH": 6,
    "ID": 6,
    "MY": 6,
    "BN": 6,
    "SG": 6,
    "TW": 6,
    "HK": 6,
    "MO": 6,
    "MN": 6,
    "KP": 6,
    "ET": 6,
    "ER": 6,
    "DJ": 6,
    "SO": 6,
    "KE": 6,
    "UG": 6,
    "TZ": 6,
    "RW": 6,
    "BI": 6,
    "MW": 6,
    "ZM": 6,
    "ZW": 6,
    "BW": 6,
    "NA": 6,
    "ZA": 6,
    "SZ": 6,
    "LS": 6,
    "MZ": 6,
    "MG": 6,
    "MU": 6,
    "SC": 6,
    "KM": 6,
    "YT": 6,
    "RE": 6,
    "MR": 6,
    "ML": 6,
    "BF": 6,
    "NE": 6,
    "TD": 6,
    "CF": 6,
    "CM": 6,
    "GQ": 6,
    "GA": 6,
    "CG": 6,
    "CD": 6,
    "AO": 6,
    "ST": 6,
    "GH": 6,
    "TG": 6,
    "BJ": 6,
    "NG": 6,
    "CI": 6,
    "LR": 6,
    "SL": 6,
    "GN": 6,
    "GW": 6,
    "SN": 6,
    "GM": 6,
    "CV": 6,
    # Monday-first countries (most of the world) - default to 0
    # Europe, most of Asia, Africa, Oceania, South America (except Brazil)
}


def get_country_first_weekday(country_code: str | None = None) -> int:
    """Get the first weekday for a country (0=Monday, 6=Sunday).

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'US', 'GB')

    Returns:
        0 for Monday-first countries, 6 for Sunday-first countries
    """
    if not country_code:
        return 0  # Default to Monday

    return COUNTRY_FIRST_WEEKDAY.get(country_code.upper(), 0)


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
    # Check for required fields
    required_fields = ["start_month", "start_day", "end_month", "end_day"]
    if not all(field in schedule for field in required_fields):
        return []

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

    If day_of_week fields are not specified, the schedule applies to the whole week.
    """
    # Check for required fields (day_of_week fields are now optional)
    required_fields = ["start_month", "start_week", "end_month", "end_week"]
    if not all(field in schedule for field in required_fields):
        return []

    start_month = schedule["start_month"]
    start_week = schedule["start_week"]
    start_day_of_week = schedule.get("start_day_of_week")
    end_month = schedule["end_month"]
    end_week = schedule["end_week"]
    end_day_of_week = schedule.get("end_day_of_week")

    # Get country code for determining first weekday
    country_code = schedule.get("country_code")
    first_weekday = get_country_first_weekday(country_code)

    # Get week types (partial or full) for start and end weeks
    start_week_type = schedule.get("start_week_type", "partial")
    end_week_type = schedule.get("end_week_type", "partial")

    try:
        # If no specific days are specified, use the whole week
        if start_day_of_week is None and end_day_of_week is None:
            # Get the start of the specified week
            week_start_date = _get_week_start(
                year, start_month, start_week, first_weekday, start_week_type
            )
            if not week_start_date:
                return []

            # Get the end of the specified week
            if end_month < start_month:
                # End is in next year
                week_end_date = _get_week_end(
                    year + 1, end_month, end_week, first_weekday, end_week_type
                )
            else:
                # Same year
                week_end_date = _get_week_end(
                    year, end_month, end_week, first_weekday, end_week_type
                )

            if not week_end_date:
                return []

            return [(week_start_date, week_end_date)]

        # If only start day is specified, use start day to end of week
        elif start_day_of_week is not None and end_day_of_week is None:
            start_date = _get_nth_weekday(
                year, start_month, start_week, start_day_of_week
            )
            if not start_date:
                return []

            if end_month < start_month:
                week_end_date = _get_week_end(
                    year + 1, end_month, end_week, first_weekday, end_week_type
                )
            else:
                week_end_date = _get_week_end(
                    year, end_month, end_week, first_weekday, end_week_type
                )

            if not week_end_date:
                return []

            return [(start_date, week_end_date)]

        # If only end day is specified, use start of week to end day
        elif start_day_of_week is None and end_day_of_week is not None:
            week_start_date = _get_week_start(
                year, start_month, start_week, first_weekday, start_week_type
            )
            if not week_start_date:
                return []

            if end_month < start_month:
                end_date = _get_nth_weekday(
                    year + 1, end_month, end_week, end_day_of_week
                )
            else:
                end_date = _get_nth_weekday(year, end_month, end_week, end_day_of_week)

            if not end_date:
                return []

            return [(week_start_date, end_date)]

        # Both days specified - original behavior
        else:
            start_date = _get_nth_weekday(
                year, start_month, start_week, start_day_of_week
            )
            if not start_date:
                return []

            # Only wrap to next year if end month is explicitly before start month
            if end_month < start_month:
                # End is in next year (e.g., December to January)
                end_date = _get_nth_weekday(
                    year + 1, end_month, end_week, end_day_of_week
                )
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
    # Check for required fields
    required_fields = ["month", "occurrence", "day_of_week"]
    if not all(field in schedule for field in required_fields):
        return []

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


def _get_week_start(
    year: int,
    month: int,
    occurrence: int,
    first_weekday: int = 0,
    week_type: str = "partial",
) -> date | None:
    """Get the start of the nth week in a month.

    Args:
        year: Year
        month: Month (1-12)
        occurrence: Week occurrence (0-3 for first through fourth, 4 for last)
        first_weekday: First day of week (0=Monday, 6=Sunday)
        week_type: "partial" for first week (may start in previous month),
                   "full" for first full week (entirely within month)

    Returns:
        Date of the first day of the specified week, or None if invalid
    """
    try:
        # Get first day of month
        first_day = date(year, month, 1)

        # Handle "last" occurrence
        if occurrence == 4:
            # Start from last day of month and work backwards to find last week
            last_day = calendar.monthrange(year, month)[1]
            last_date = date(year, month, last_day)

            # Find the start of the week containing the last day
            days_back = (last_date.weekday() - first_weekday) % 7
            week_start = last_date - timedelta(days=days_back)

            # Make sure it's still in the same month
            if week_start.month != month:
                # If week start is in previous month, find the first day of month that's in this week
                return date(year, month, 1)

            return week_start

        # Find the start of the first week that has any days in this month
        # Calculate how many days back from the first day to get to the week start
        days_back = (first_day.weekday() - first_weekday) % 7
        first_week_start = first_day - timedelta(days=days_back)

        # Handle week type
        if week_type == "full":
            # For "full" week type, skip to the first full week entirely within the month
            if first_week_start.month != month:
                # First week starts in previous month, so first full week is the next one
                first_week_start = first_day + timedelta(days=(7 - days_back))
        else:
            # For "partial" week type (default), use the first week even if it starts in previous month
            if first_week_start.month != month:
                first_week_start = first_day

        # Add weeks for nth occurrence
        target_week_start = first_week_start + timedelta(weeks=occurrence)

        # Verify it's still in the same month (at least partially)
        if target_week_start.month > month or (
            target_week_start.month < month and target_week_start.year >= year
        ):
            return None

        return target_week_start
    except (ValueError, OverflowError):
        return None


def _get_week_end(
    year: int,
    month: int,
    occurrence: int,
    first_weekday: int = 0,
    week_type: str = "partial",
) -> date | None:
    """Get the end of the nth week in a month.

    Args:
        year: Year
        month: Month (1-12)
        occurrence: Week occurrence (0-3 for first through fourth, 4 for last)
        first_weekday: First day of week (0=Monday, 6=Sunday)
        week_type: "partial" for first week (may start in previous month),
                   "full" for first full week (entirely within month)

    Returns:
        Date of the last day of the specified week, or None if invalid
    """
    try:
        week_start = _get_week_start(year, month, occurrence, first_weekday, week_type)
        if not week_start:
            return None

        # Calculate last day of week (6 days after first day)
        week_end = week_start + timedelta(days=6)

        # For any week, don't go beyond month boundary unless it's the last week
        last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
        if occurrence == 4 or week_end > last_day_of_month:
            week_end = min(week_end, last_day_of_month)

        return week_end
    except (ValueError, OverflowError):
        return None


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
