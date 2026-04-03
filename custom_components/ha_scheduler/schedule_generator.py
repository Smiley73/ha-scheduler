"""Schedule generator for different schedule types."""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

# Babel imports moved inside functions to avoid blocking I/O during module import

_LOGGER = logging.getLogger(__name__)

# The Gregorian calendar repeats every 400 years, including leap-year rules.
# Checking one full cycle makes overlap validation deterministic and ensures we
# catch collisions that may not occur in the next few years.
OVERLAP_VALIDATION_START_YEAR = 2000
OVERLAP_VALIDATION_YEARS = 400
HOLIDAY_OVERLAP_HORIZON = 10

# Fallback mapping for countries where Babel doesn't have locale data
# or where the locale data differs from common practice
# 0 = Monday, 6 = Sunday
COUNTRY_FIRST_WEEKDAY_FALLBACK = {
    # Countries that commonly use Sunday as first day but may not be in Babel
    "JP": 6,  # Japan - commonly uses Sunday in business/calendar contexts
    "KR": 6,  # South Korea
    "MX": 6,  # Mexico
    "IL": 6,  # Israel
    "SA": 6,  # Saudi Arabia
    "AE": 6,  # UAE
    "EG": 6,  # Egypt
    "PH": 6,  # Philippines
    "TW": 6,  # Taiwan
    "HK": 6,  # Hong Kong
    "SG": 6,  # Singapore
    "TH": 6,  # Thailand
    "MY": 6,  # Malaysia
    "ID": 6,  # Indonesia
    "VN": 6,  # Vietnam
    # Add more as needed for countries not well-covered by Babel
}

type OverlapSignature = tuple[int | str | None, ...]


def _get_fallback_weekday(
    country_code: str, country_upper: str, error: Exception | None = None
) -> int:
    """Get weekday from fallback mapping or return default.

    Args:
        country_code: Original country code for logging
        country_upper: Uppercase country code for lookup
        error: Optional error that triggered the fallback

    Returns:
        First weekday from mapping or 0 (Monday) as default
    """
    if country_upper in COUNTRY_FIRST_WEEKDAY_FALLBACK:
        _LOGGER.debug("Using fallback weekday data for country %s", country_code)
        return COUNTRY_FIRST_WEEKDAY_FALLBACK[country_upper]

    if error:
        _LOGGER.debug(
            "Could not determine first weekday for country %s: %s. Using Monday as default.",
            country_code,
            error,
        )
    return 0  # Default to Monday


def get_country_first_weekday(country_code: str | None = None) -> int:
    """Get the first weekday for a country (0=Monday, 6=Sunday).

    Uses Babel's locale data to determine the first day of the week for different countries.
    This provides more comprehensive and up-to-date locale information than a static mapping.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'US', 'GB')

    Returns:
        0 for Monday-first countries, 6 for Sunday-first countries
    """
    if not country_code:
        return 0  # Default to Monday

    country_upper = country_code.upper()

    try:
        # Lazy import to avoid blocking I/O during module import
        from babel import Locale

        # Try to create a locale from the country code
        # We use English as the language since we only care about the territory
        locale_str = f"en_{country_upper}"
        locale = Locale.parse(locale_str)

        # Get the first day of the week
        # Babel uses 0=Monday, 6=Sunday which matches our expected format
        first_day = locale.first_week_day
        return first_day

    except ImportError as e:
        _LOGGER.debug("Babel not available for weekday detection: %s", e)
        return _get_fallback_weekday(country_code, country_upper)

    except Exception as e:
        # Catch Babel's UnknownLocaleError (direct Exception subclass), ValueError,
        # AttributeError, TypeError, and any other locale-related errors
        # Note: We use broad Exception here because babel.core.UnknownLocaleError
        # is a direct subclass of Exception and we can't import it conditionally
        # Try alternative locale formats for countries that might not have en_XX
        try:
            from babel import Locale

            # Some countries might have their own primary language locale
            locale = Locale.parse(country_code.lower())
            first_day = locale.first_week_day
            return first_day
        except Exception:
            # Any locale-related error in fallback - use mapping or default
            pass

        return _get_fallback_weekday(country_code, country_upper, e)


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
    if schedule_type == "holiday":
        return _generate_by_holiday(schedule, year)

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


def _calculate_end_year(end_month: int, start_month: int, year: int) -> int:
    """Calculate the year for the end date based on month wrapping."""
    return year + 1 if end_month < start_month else year


def _get_effective_week_type(
    start_month: int, end_month: int, start_week_type: str, end_week_type: str
) -> str:
    """Determine effective week type for end week."""
    return start_week_type if start_month == end_month else end_week_type


def _build_date_range(
    start_date: date | None,
    end_date: date | None,
) -> list[tuple[date, date]]:
    """Build a single date range when the bounds form a valid interval."""
    if not start_date or not end_date or start_date > end_date:
        return []
    return [(start_date, end_date)]


def _generate_whole_week_range(
    year: int,
    start_month: int,
    start_week: int,
    end_month: int,
    end_week: int,
    first_weekday: int,
    start_week_type: str,
    end_week_type: str,
) -> list[tuple[date, date]]:
    """Generate date range for a whole week schedule (no specific days)."""
    week_start_date = _get_week_start(
        year, start_month, start_week, first_weekday, start_week_type
    )
    if not week_start_date:
        return []

    effective_end_week_type = _get_effective_week_type(
        start_month, end_month, start_week_type, end_week_type
    )
    end_year = _calculate_end_year(end_month, start_month, year)

    week_end_date = _get_week_end(
        end_year, end_month, end_week, first_weekday, effective_end_week_type
    )
    return _build_date_range(week_start_date, week_end_date)


def _generate_start_day_to_end_week(
    year: int,
    start_month: int,
    start_week: int,
    start_day_of_week: int,
    end_month: int,
    end_week: int,
    first_weekday: int,
    start_week_type: str,
    end_week_type: str,
) -> list[tuple[date, date]]:
    """Generate date range from a specific start day to end of week."""
    start_date = _get_weekday_in_week(
        year, start_month, start_week, start_day_of_week, first_weekday, start_week_type
    )
    if not start_date:
        return []

    effective_end_week_type = _get_effective_week_type(
        start_month, end_month, start_week_type, end_week_type
    )
    end_year = _calculate_end_year(end_month, start_month, year)
    week_end_date = _get_week_end(
        end_year, end_month, end_week, first_weekday, effective_end_week_type
    )

    return _build_date_range(start_date, week_end_date)


def _generate_week_start_to_end_day(
    year: int,
    start_month: int,
    start_week: int,
    end_month: int,
    end_week: int,
    end_day_of_week: int,
    first_weekday: int,
    start_week_type: str,
    end_week_type: str,
) -> list[tuple[date, date]]:
    """Generate date range from start of week to a specific end day."""
    week_start_date = _get_week_start(
        year, start_month, start_week, first_weekday, start_week_type
    )
    if not week_start_date:
        return []

    effective_end_week_type = _get_effective_week_type(
        start_month, end_month, start_week_type, end_week_type
    )
    end_year = _calculate_end_year(end_month, start_month, year)
    end_date = _get_weekday_in_week(
        end_year,
        end_month,
        end_week,
        end_day_of_week,
        first_weekday,
        effective_end_week_type,
    )

    return _build_date_range(week_start_date, end_date)


def _generate_specific_day_range(
    year: int,
    start_month: int,
    start_week: int,
    start_day_of_week: int,
    end_month: int,
    end_week: int,
    end_day_of_week: int,
    first_weekday: int,
    start_week_type: str,
    end_week_type: str,
) -> list[tuple[date, date]]:
    """Generate date range between two specific days of weeks."""
    # At this point, both day_of_week values are guaranteed to be not None
    start_date = _get_weekday_in_week(
        year,
        start_month,
        start_week,
        int(start_day_of_week),
        first_weekday,
        start_week_type,
    )
    if not start_date:
        return []

    end_year = _calculate_end_year(end_month, start_month, year)
    effective_end_week_type = _get_effective_week_type(
        start_month, end_month, start_week_type, end_week_type
    )

    end_date = _get_weekday_in_week(
        end_year,
        end_month,
        end_week,
        int(end_day_of_week),
        first_weekday,
        effective_end_week_type,
    )
    return _build_date_range(start_date, end_date)


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
        # Dispatch to appropriate helper based on which day_of_week fields are specified
        if start_day_of_week is None and end_day_of_week is None:
            # Whole week schedule
            return _generate_whole_week_range(
                year,
                start_month,
                start_week,
                end_month,
                end_week,
                first_weekday,
                start_week_type,
                end_week_type,
            )
        elif start_day_of_week is not None and end_day_of_week is None:
            # Start day to end of week
            return _generate_start_day_to_end_week(
                year,
                start_month,
                start_week,
                start_day_of_week,
                end_month,
                end_week,
                first_weekday,
                start_week_type,
                end_week_type,
            )
        elif start_day_of_week is None and end_day_of_week is not None:
            # Start of week to end day
            return _generate_week_start_to_end_day(
                year,
                start_month,
                start_week,
                end_month,
                end_week,
                end_day_of_week,
                first_weekday,
                start_week_type,
                end_week_type,
            )
        else:
            # Both days specified
            if start_day_of_week is None or end_day_of_week is None:
                return []  # Unreachable given the preceding branches; satisfies the type checker
            return _generate_specific_day_range(
                year,
                start_month,
                start_week,
                start_day_of_week,
                end_month,
                end_week,
                end_day_of_week,
                first_weekday,
                start_week_type,
                end_week_type,
            )

    except (ValueError, KeyError):
        return []


def week_schedule_has_valid_ranges(schedule: dict[str, Any]) -> bool:
    """Return whether a week schedule generates a valid range every year."""
    if schedule.get("schedule_type") != "week":
        return False

    return _week_schedule_has_valid_ranges(_get_overlap_signature(schedule))


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


def _generate_by_holiday(
    schedule: dict[str, Any], year: int
) -> list[tuple[date, date]]:
    """Generate dates for a holiday-backed schedule."""
    try:
        from .holiday_importer import generate_holiday_schedule_dates
    except ImportError:
        return []

    return generate_holiday_schedule_dates(schedule, year)


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

        # Find the start of the first calendar week that has any days in this month
        # Calculate how many days back from the first day to get to the week start
        days_back = (first_day.weekday() - first_weekday) % 7
        first_calendar_week_start = first_day - timedelta(days=days_back)

        # Handle week type for the first week (occurrence 0)
        if occurrence == 0:
            if week_type == "full":
                # For "full" week type, skip to the first full week entirely within the month
                if first_calendar_week_start.month != month:
                    # First week starts in previous month, so first full week is the next one
                    return first_calendar_week_start + timedelta(weeks=1)
                else:
                    return first_calendar_week_start
            else:
                # For "partial" week type (default), use the first week even if it starts in previous month
                if first_calendar_week_start.month != month:
                    # Return the first day of the month as the start of the partial week
                    return first_day
                else:
                    return first_calendar_week_start

        # For subsequent weeks (occurrence > 0), calculate based on the actual first week
        if week_type == "full":
            # For full type, subsequent weeks are based on the first full week
            if first_calendar_week_start.month != month:
                # First full week starts in the next calendar week
                first_full_week_start = first_calendar_week_start + timedelta(weeks=1)
            else:
                first_full_week_start = first_calendar_week_start
            target_week_start = first_full_week_start + timedelta(weeks=occurrence)
        else:
            # For partial type, use calendar week boundaries
            target_week_start = first_calendar_week_start + timedelta(weeks=occurrence)

            # For partial type first week that was adjusted to start on first day of month,
            # we need to adjust subsequent weeks to align with proper calendar weeks
            if first_calendar_week_start.month != month and occurrence > 0:
                # The first week was adjusted to start on the first day of month
                # But subsequent weeks should follow calendar week boundaries
                # So we need to find the next Sunday (or Monday) after the first day
                days_to_next_week_start = (first_weekday - first_day.weekday()) % 7
                if days_to_next_week_start == 0:
                    days_to_next_week_start = (
                        7  # If first day is already the week start day, go to next week
                    )

                next_calendar_week_start = first_day + timedelta(
                    days=days_to_next_week_start
                )
                target_week_start = next_calendar_week_start + timedelta(
                    weeks=occurrence - 1
                )

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

        # Get first day of month to check if this is a partial first week
        first_day = date(year, month, 1)

        # Calculate the theoretical calendar week end (6 days after calendar week start)
        # Find the start of the calendar week that contains this week_start
        days_back = (week_start.weekday() - first_weekday) % 7
        calendar_week_start = week_start - timedelta(days=days_back)
        calendar_week_end = calendar_week_start + timedelta(days=6)

        # For the first week (occurrence 0) with partial type,
        # if the week_start was adjusted to be the first day of month,
        # we need to find the actual end of that partial week
        if (
            occurrence == 0
            and week_type == "partial"
            and week_start == first_day
            and calendar_week_start.month != month
        ):
            # This is a partial first week that starts mid-calendar-week
            # The end should be the end of the calendar week or end of month, whichever is earlier
            last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
            week_end = min(calendar_week_end, last_day_of_month)
        else:
            # For all other cases, use the full calendar week end
            week_end = calendar_week_end

        # Don't go beyond month boundary for any week except the last week
        last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
        if occurrence == 4 or week_end > last_day_of_month:
            week_end = min(week_end, last_day_of_month)

        return week_end
    except (ValueError, OverflowError):
        return None


def _get_weekday_in_week(
    year: int,
    month: int,
    week_occurrence: int,
    day_of_week: int,
    first_weekday: int = 0,
    week_type: str = "partial",
) -> date | None:
    """Get a specific weekday within a specific week of a month.

    Args:
        year: Year
        month: Month (1-12)
        week_occurrence: Week occurrence (0-3 for first through fourth, 4 for last)
        day_of_week: Day of week (0-6 for Monday through Sunday)
        first_weekday: First day of week (0=Monday, 6=Sunday)
        week_type: "partial" or "full" for first week handling

    Returns:
        Date of the specific weekday in the specific week, or None if it doesn't exist
    """
    try:
        if week_occurrence == 4:
            # For "last week", day-specific selections mean the last occurrence
            # of that weekday within the month.
            return _get_nth_weekday(year, month, 4, day_of_week)

        # Get the start and end of the specified week
        week_start = _get_week_start(
            year, month, week_occurrence, first_weekday, week_type
        )
        week_end = _get_week_end(year, month, week_occurrence, first_weekday, week_type)

        if not week_start or not week_end:
            return None

        # Check each day in the week to find the requested weekday
        current_date = week_start
        while current_date <= week_end:
            if current_date.weekday() == day_of_week:
                return current_date
            current_date += timedelta(days=1)

        # The requested weekday doesn't exist in this week
        return None
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

    Gregorian schedules are validated across a full 400-year cycle to keep
    overlap checks deterministic. Holiday-backed schedules use a bounded,
    provider-backed horizon because their dates come from the holidays library.

    Returns:
        Tuple of (has_overlap, conflicting_schedule_name)
    """
    # Validate schedule has required fields
    if "schedule_type" not in schedule:
        return (False, None)

    new_signature = _get_overlap_signature(schedule)
    cached_new_dates: tuple[tuple[date, date], ...] | None = None

    if _uses_deterministic_overlap_cycle(new_signature):
        cached_new_dates = _generate_overlap_ranges(new_signature)
        if not cached_new_dates:
            return (False, None)

    # Check against existing schedules
    for existing in existing_schedules:
        if exclude_uid and existing.get("uid") == exclude_uid:
            continue

        existing_signature = _get_overlap_signature(existing)

        if _uses_deterministic_overlap_cycle(
            new_signature
        ) and _uses_deterministic_overlap_cycle(existing_signature):
            new_dates = cached_new_dates or ()
            existing_dates = _generate_overlap_ranges(existing_signature)
            if not existing_dates:
                continue
        else:
            overlap_years = _get_overlap_years(schedule, existing)
            new_dates = tuple(_generate_dates_for_years(schedule, overlap_years))
            if not new_dates:
                continue

            existing_dates = tuple(_generate_dates_for_years(existing, overlap_years))
            if not existing_dates:
                continue

        # Check for overlaps across all generated date ranges
        for new_start, new_end in new_dates:
            for exist_start, exist_end in existing_dates:
                if new_start <= exist_end and new_end >= exist_start:
                    return (True, existing.get("name", "Unknown"))

    return (False, None)


def _get_overlap_signature(schedule: dict[str, Any]) -> OverlapSignature:
    """Return the date-relevant schedule fields as a stable cache key."""
    schedule_type = schedule.get("schedule_type")

    if schedule_type == "date":
        return (
            "date",
            schedule.get("start_month"),
            schedule.get("start_day"),
            schedule.get("end_month"),
            schedule.get("end_day"),
        )

    if schedule_type == "week":
        country_code = schedule.get("country_code")
        normalized_country = (
            country_code.upper() if isinstance(country_code, str) else None
        )
        return (
            "week",
            schedule.get("start_month"),
            schedule.get("start_week"),
            schedule.get("start_day_of_week"),
            schedule.get("end_month"),
            schedule.get("end_week"),
            schedule.get("end_day_of_week"),
            schedule.get("start_week_type", "partial"),
            schedule.get("end_week_type", "partial"),
            normalized_country,
        )

    if schedule_type == "nth-day":
        return (
            "nth-day",
            schedule.get("month"),
            schedule.get("occurrence"),
            schedule.get("day_of_week"),
            schedule.get("start_offset", 0),
            schedule.get("end_offset", 0),
        )

    if schedule_type == "holiday":
        country_code = schedule.get("country_code")
        normalized_country = (
            country_code.upper() if isinstance(country_code, str) else None
        )
        category = schedule.get("category")
        holiday_name = schedule.get("holiday_name")
        return (
            "holiday",
            normalized_country,
            str(category) if category is not None else None,
            str(holiday_name) if holiday_name is not None else None,
            str(schedule.get("name_lookup", "iexact")),
            schedule.get("start_offset", 0),
            schedule.get("end_offset", 0),
        )

    return (schedule_type,)


def _schedule_from_signature(signature: OverlapSignature) -> dict[str, Any] | None:
    """Rebuild the date-relevant schedule fields from a cache signature."""
    if not signature:
        return None

    schedule_type = signature[0]

    if schedule_type == "date":
        _, start_month, start_day, end_month, end_day = signature
        return {
            "schedule_type": "date",
            "start_month": start_month,
            "start_day": start_day,
            "end_month": end_month,
            "end_day": end_day,
        }

    if schedule_type == "week":
        (
            _,
            start_month,
            start_week,
            start_day_of_week,
            end_month,
            end_week,
            end_day_of_week,
            start_week_type,
            end_week_type,
            country_code,
        ) = signature
        schedule = {
            "schedule_type": "week",
            "start_month": start_month,
            "start_week": start_week,
            "end_month": end_month,
            "end_week": end_week,
            "start_week_type": start_week_type,
            "end_week_type": end_week_type,
        }
        if start_day_of_week is not None:
            schedule["start_day_of_week"] = start_day_of_week
        if end_day_of_week is not None:
            schedule["end_day_of_week"] = end_day_of_week
        if country_code is not None:
            schedule["country_code"] = country_code
        return schedule

    if schedule_type == "nth-day":
        _, month, occurrence, day_of_week, start_offset, end_offset = signature
        return {
            "schedule_type": "nth-day",
            "month": month,
            "occurrence": occurrence,
            "day_of_week": day_of_week,
            "start_offset": start_offset,
            "end_offset": end_offset,
        }

    if schedule_type == "holiday":
        (
            _,
            country_code,
            category,
            holiday_name,
            lookup,
            start_offset,
            end_offset,
        ) = signature
        schedule = {
            "schedule_type": "holiday",
            "country_code": country_code,
            "holiday_name": holiday_name,
            "name_lookup": lookup,
            "start_offset": start_offset,
            "end_offset": end_offset,
        }
        if category is not None:
            schedule["category"] = category
        return schedule

    return None


@lru_cache(maxsize=1024)
def _generate_overlap_ranges(
    signature: OverlapSignature,
) -> tuple[tuple[date, date], ...]:
    """Generate all date ranges needed for deterministic overlap checks."""
    if not (schedule := _schedule_from_signature(signature)):
        return ()

    all_ranges: list[tuple[date, date]] = []
    for year in range(
        OVERLAP_VALIDATION_START_YEAR,
        OVERLAP_VALIDATION_START_YEAR + OVERLAP_VALIDATION_YEARS,
    ):
        all_ranges.extend(generate_schedule_dates(schedule, year))

    return tuple(all_ranges)


@lru_cache(maxsize=1024)
def _week_schedule_has_valid_ranges(signature: OverlapSignature) -> bool:
    """Return whether a week schedule produces a valid range every year."""
    if not (schedule := _schedule_from_signature(signature)):
        return False

    for year in range(
        OVERLAP_VALIDATION_START_YEAR,
        OVERLAP_VALIDATION_START_YEAR + OVERLAP_VALIDATION_YEARS,
    ):
        date_ranges = generate_schedule_dates(schedule, year)
        if not date_ranges:
            return False

        start_date, end_date = date_ranges[0]
        if start_date > end_date:
            return False

    return True


def _uses_deterministic_overlap_cycle(signature: OverlapSignature) -> bool:
    """Return whether a schedule signature can use the 400-year cycle cache."""
    if not signature:
        return False

    return signature[0] in {"date", "week", "nth-day"}


def _get_overlap_years(
    schedule: dict[str, Any], existing_schedule: dict[str, Any]
) -> range:
    """Return the bounded year range used for holiday-backed overlap checks."""
    current_year = date.today().year

    if (
        schedule.get("schedule_type") == "holiday"
        or existing_schedule.get("schedule_type") == "holiday"
    ):
        return range(current_year, current_year + HOLIDAY_OVERLAP_HORIZON + 1)

    return range(
        OVERLAP_VALIDATION_START_YEAR,
        OVERLAP_VALIDATION_START_YEAR + OVERLAP_VALIDATION_YEARS,
    )


def _generate_dates_for_years(
    schedule: dict[str, Any], years: range
) -> list[tuple[date, date]]:
    """Generate schedule dates for each year in a range."""
    generated_dates: list[tuple[date, date]] = []

    for year in years:
        generated_dates.extend(generate_schedule_dates(schedule, year))

    return generated_dates
