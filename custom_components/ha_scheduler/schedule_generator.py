"""Schedule generator for different schedule types."""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from .const import (
    SCHEDULE_TYPE_DATE,
    SCHEDULE_TYPE_HOLIDAY,
    SCHEDULE_TYPE_NTH_DAY,
    SCHEDULE_TYPE_WEEK,
)
from .holiday_importer import generate_holiday_schedule_dates

# Babel imports moved inside functions to avoid blocking I/O during module import

_LOGGER = logging.getLogger(__name__)

# The Gregorian calendar repeats every 400 years, including leap-year rules.
# Checking one full cycle makes overlap validation deterministic and ensures we
# catch collisions that may not occur in the next few years.
OVERLAP_VALIDATION_START_YEAR = 2000
OVERLAP_VALIDATION_YEARS = 400
OVERLAP_VALIDATION_RANGE = range(
    OVERLAP_VALIDATION_START_YEAR,
    OVERLAP_VALIDATION_START_YEAR + OVERLAP_VALIDATION_YEARS,
)
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

type OverlapSignature = tuple[tuple[str, Any], ...]


def get_country_first_weekday(country_code: str | None = None) -> int:
    """Return the first weekday for a country (0=Monday, 6=Sunday).

    Uses Babel's locale data, falling back to a static table and then Monday.
    """
    if not country_code:
        return 0

    country_upper = country_code.upper()

    try:
        # Lazy import to avoid blocking I/O during module import
        from babel import Locale

        # Only the territory matters, so use English as the language.
        return Locale.parse(f"en_{country_upper}").first_week_day

    except Exception as e:  # noqa: BLE001 - babel.core.UnknownLocaleError is a direct Exception subclass
        try:
            # Some countries only have a locale under their own code.
            return Locale.parse(country_code.lower()).first_week_day
        except Exception:  # noqa: BLE001, S110 - last-resort fallback below
            pass

        if country_upper in COUNTRY_FIRST_WEEKDAY_FALLBACK:
            _LOGGER.debug("Using fallback weekday data for country %s", country_code)
            return COUNTRY_FIRST_WEEKDAY_FALLBACK[country_upper]

        _LOGGER.debug(
            "Could not determine first weekday for country %s: %s. Using Monday as default.",
            country_code,
            e,
        )
        return 0


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
    schedule_type = schedule.get("schedule_type", SCHEDULE_TYPE_DATE)

    if schedule_type == SCHEDULE_TYPE_DATE:
        return _generate_by_date(schedule, year)
    if schedule_type == SCHEDULE_TYPE_WEEK:
        return _generate_by_week(schedule, year)
    if schedule_type == SCHEDULE_TYPE_NTH_DAY:
        return _generate_by_nth_day(schedule, year)
    if schedule_type == SCHEDULE_TYPE_HOLIDAY:
        return generate_holiday_schedule_dates(schedule, year)

    return []


def _generate_by_date(schedule: dict[str, Any], year: int) -> list[tuple[date, date]]:
    """Generate dates for 'by_date' schedule type.

    Handles year wrapping (e.g., Dec 15 to Jan 15).
    """
    required_fields = ["start_month", "start_day", "end_month", "end_day"]
    if not all(field in schedule for field in required_fields):
        return []

    start_month = schedule["start_month"]
    start_day = schedule["start_day"]
    end_month = schedule["end_month"]
    end_day = schedule["end_day"]

    try:
        # Days past the end of the month are clamped to its last day.
        start_date = date(
            year, start_month, min(start_day, calendar.monthrange(year, start_month)[1])
        )

        wraps = end_month < start_month or (
            end_month == start_month and end_day < start_day
        )
        end_year = year + 1 if wraps else year
        end_date = date(
            end_year,
            end_month,
            min(end_day, calendar.monthrange(end_year, end_month)[1]),
        )

        return [(start_date, end_date)]
    except (ValueError, KeyError):
        return []


def _resolve_end_week_type(schedule: dict[str, Any]) -> str:
    """Resolve the effective week type for the end week of a week schedule.

    An explicitly stored ``end_week_type`` always wins. When absent, a
    same-month schedule inherits the start week's type (the two bounds refer
    to the same month's week structure); otherwise default to "partial".
    """
    if (end_week_type := schedule.get("end_week_type")) is not None:
        return str(end_week_type)

    if schedule.get("start_month") == schedule.get("end_month"):
        return str(schedule.get("start_week_type", "partial"))

    return "partial"


def _generate_by_week(schedule: dict[str, Any], year: int) -> list[tuple[date, date]]:
    """Generate dates for 'by_week' schedule type.

    Handles year wrapping only when end_month < start_month
    (e.g., last Monday of December to first Friday of January).

    A missing day_of_week bound means the whole week: the start of the start
    week, or the end of the end week.
    """
    required_fields = ["start_month", "start_week", "end_month", "end_week"]
    if not all(field in schedule for field in required_fields):
        return []

    start_month = schedule["start_month"]
    start_week = schedule["start_week"]
    start_day_of_week = schedule.get("start_day_of_week")
    end_month = schedule["end_month"]
    end_week = schedule["end_week"]
    end_day_of_week = schedule.get("end_day_of_week")

    first_weekday = get_country_first_weekday(schedule.get("country_code"))
    start_week_type = schedule.get("start_week_type", "partial")
    end_week_type = _resolve_end_week_type(schedule)

    try:
        if start_day_of_week is None:
            start_date = _get_week_start(
                year, start_month, start_week, first_weekday, start_week_type
            )
        else:
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

        end_year = year + 1 if end_month < start_month else year
        if end_day_of_week is None:
            end_date = _get_week_end(
                end_year, end_month, end_week, first_weekday, end_week_type
            )
        else:
            end_date = _get_weekday_in_week(
                end_year,
                end_month,
                end_week,
                int(end_day_of_week),
                first_weekday,
                end_week_type,
            )
    except (ValueError, KeyError):
        return []

    if not end_date or start_date > end_date:
        return []
    return [(start_date, end_date)]


def week_schedule_has_valid_ranges(schedule: dict[str, Any]) -> bool:
    """Return whether a week schedule generates a valid range every year."""
    if schedule.get("schedule_type") != SCHEDULE_TYPE_WEEK:
        return False

    # A week schedule yields at most one range per year.
    ranges = _generate_overlap_ranges(_get_overlap_signature(schedule))
    return len(ranges) == OVERLAP_VALIDATION_YEARS


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
    """Get the start of the nth week in a month, or None if it doesn't exist.

    Occurrence 4 means the last week. ``partial`` counts a first week that
    starts in the previous month; ``full`` only counts weeks entirely within
    the month.
    """
    try:
        first_day = date(year, month, 1)

        if occurrence == 4:
            last_date = date(year, month, calendar.monthrange(year, month)[1])
            days_back = (last_date.weekday() - first_weekday) % 7
            week_start = last_date - timedelta(days=days_back)

            if (
                week_start.month != month
            ):  # pragma: no cover - the last-week start is at most 6 days before the month's last day, i.e. day >= 22, so it can't cross into the previous month
                # If week start is in previous month, find the first day of month that's in this week
                return date(year, month, 1)

            return week_start

        # Start of the first calendar week that has any days in this month
        days_back = (first_day.weekday() - first_weekday) % 7
        first_calendar_week_start = first_day - timedelta(days=days_back)

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
                if (
                    days_to_next_week_start == 0
                ):  # pragma: no cover - the enclosing branch requires the first calendar week to start in the previous month, which forces days_back != 0
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
    """Get the end of the nth week in a month, clamped to the month's last day.

    Occurrence 4 means the last week; ``week_type`` is as in `_get_week_start`.
    """
    try:
        week_start = _get_week_start(year, month, occurrence, first_weekday, week_type)
        if not week_start:
            return None

        days_back = (week_start.weekday() - first_weekday) % 7
        calendar_week_end = week_start - timedelta(days=days_back) + timedelta(days=6)
        last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
        return min(calendar_week_end, last_day_of_month)
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
    """Get a weekday (0=Monday) within the nth week of a month, or None."""
    try:
        if week_occurrence == 4:
            # For "last week", day-specific selections mean the last occurrence
            # of that weekday within the month.
            return _get_nth_weekday(year, month, 4, day_of_week)

        week_start = _get_week_start(
            year, month, week_occurrence, first_weekday, week_type
        )
        week_end = _get_week_end(year, month, week_occurrence, first_weekday, week_type)

        if not week_start or not week_end:
            return None

        current_date = week_start
        while current_date <= week_end:
            if current_date.weekday() == day_of_week:
                return current_date
            current_date += timedelta(days=1)

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
        first_day = date(year, month, 1)

        if occurrence == 4:
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
    today: date | None = None,
) -> tuple[bool, str | None]:
    """Return (has_overlap, conflicting_schedule_name) against existing schedules.

    Gregorian schedules are validated across a full 400-year cycle to keep
    overlap checks deterministic. Holiday-backed schedules use a bounded,
    provider-backed horizon because their dates come from the holidays library.
    ``exclude_uid`` skips the schedule being edited. Callers inside Home
    Assistant should pass ``today=dt_util.now().date()`` so the configured
    timezone is honored; it defaults to the system date.
    """
    if "schedule_type" not in schedule:
        return (False, None)

    new_signature = _get_overlap_signature(schedule)
    cached_new_dates: tuple[tuple[date, date], ...] = ()

    if _uses_deterministic_overlap_cycle(new_signature):
        cached_new_dates = _generate_overlap_ranges(new_signature)
        if not cached_new_dates:
            return (False, None)

    for existing in existing_schedules:
        if exclude_uid and existing.get("uid") == exclude_uid:
            continue

        existing_signature = _get_overlap_signature(existing)

        if _uses_deterministic_overlap_cycle(
            new_signature
        ) and _uses_deterministic_overlap_cycle(existing_signature):
            new_dates = cached_new_dates
            existing_dates = _generate_overlap_ranges(existing_signature)
            if not existing_dates:
                continue
        else:
            overlap_years = _get_overlap_years(schedule, existing, today)
            new_dates = _generate_dates_for_years(schedule, overlap_years)
            if not new_dates:
                continue

            existing_dates = _generate_dates_for_years(existing, overlap_years)
            if not existing_dates:
                continue

        for new_start, new_end in new_dates:
            for exist_start, exist_end in existing_dates:
                if new_start <= exist_end and new_end >= exist_start:
                    return (True, existing.get("name", "Unknown"))

    return (False, None)


def _get_overlap_signature(schedule: dict[str, Any]) -> OverlapSignature:
    """Return the date-relevant schedule fields as a hashable cache key.

    ``dict()`` of the key is the schedule that `_generate_overlap_ranges`
    generates from. Only date, week and nth-day schedules carry fields:
    other types are never cached, so their key holds just the type.
    """
    schedule_type = schedule.get("schedule_type")
    fields: dict[str, Any] = {"schedule_type": schedule_type}

    if schedule_type == SCHEDULE_TYPE_DATE:
        for field in ("start_month", "start_day", "end_month", "end_day"):
            fields[field] = schedule.get(field)

    elif schedule_type == SCHEDULE_TYPE_WEEK:
        for field in ("start_month", "start_week", "end_month", "end_week"):
            fields[field] = schedule.get(field)
        for field in ("start_day_of_week", "end_day_of_week"):
            if schedule.get(field) is not None:
                fields[field] = schedule[field]
        fields["start_week_type"] = schedule.get("start_week_type", "partial")
        # Store the resolved value so cached overlap checks agree with
        # direct generation for schedules without a stored end_week_type.
        fields["end_week_type"] = _resolve_end_week_type(schedule)
        if isinstance(country_code := schedule.get("country_code"), str):
            fields["country_code"] = country_code.upper()

    elif schedule_type == SCHEDULE_TYPE_NTH_DAY:
        for field in ("month", "occurrence", "day_of_week"):
            fields[field] = schedule.get(field)
        fields["start_offset"] = schedule.get("start_offset", 0)
        fields["end_offset"] = schedule.get("end_offset", 0)

    return tuple(fields.items())


@lru_cache(maxsize=1024)
def _generate_overlap_ranges(
    signature: OverlapSignature,
) -> tuple[tuple[date, date], ...]:
    """Generate all date ranges needed for deterministic overlap checks."""
    return _generate_dates_for_years(dict(signature), OVERLAP_VALIDATION_RANGE)


def _uses_deterministic_overlap_cycle(signature: OverlapSignature) -> bool:
    """Return whether a schedule signature can use the 400-year cycle cache."""
    return signature[0][1] in {
        SCHEDULE_TYPE_DATE,
        SCHEDULE_TYPE_WEEK,
        SCHEDULE_TYPE_NTH_DAY,
    }


def _get_overlap_years(
    schedule: dict[str, Any],
    existing_schedule: dict[str, Any],
    today: date | None = None,
) -> range:
    """Return the bounded year range used for holiday-backed overlap checks."""
    current_year = (today or date.today()).year

    if (
        schedule.get("schedule_type") == SCHEDULE_TYPE_HOLIDAY
        or existing_schedule.get("schedule_type") == SCHEDULE_TYPE_HOLIDAY
    ):
        return range(current_year, current_year + HOLIDAY_OVERLAP_HORIZON + 1)

    return OVERLAP_VALIDATION_RANGE


def _generate_dates_for_years(
    schedule: dict[str, Any], years: range
) -> tuple[tuple[date, date], ...]:
    """Generate schedule dates for each year in a range."""
    return tuple(
        date_range
        for year in years
        for date_range in generate_schedule_dates(schedule, year)
    )
