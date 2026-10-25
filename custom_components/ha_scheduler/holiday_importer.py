"""Holiday schedule importer for HA Scheduler."""

from __future__ import annotations

import asyncio
import importlib
import logging
from collections.abc import Iterable
from datetime import date, timedelta
from functools import lru_cache
from types import ModuleType
from typing import Any

from .const import (
    CALENDAR_YEAR_LOOKAROUND,
    DAY_NAMES_DISPLAY,
    MONTH_NAMES_DISPLAY,
    OCCURRENCE_NAMES_DISPLAY,
    SCHEDULE_TYPE_DATE,
    SCHEDULE_TYPE_HOLIDAY,
    SCHEDULE_TYPE_NTH_DAY,
)

# Babel and holidays do blocking I/O on first use, so they are imported lazily
# inside functions, never at module level (this module loads on the event loop).

_LOGGER = logging.getLogger(__name__)


def format_date_localized(date_obj: date, locale_code: str | None = None) -> str:
    """Format a date as "Month Day" (e.g. "January 1"), defaulting to English."""
    try:
        from babel import Locale
        from babel.dates import format_date

        locale = Locale.parse(locale_code or "en")
        return format_date(date_obj, format="MMMM d", locale=locale)
    except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
        # Catches ImportError, UnknownLocaleError, ValueError, etc.
        _LOGGER.debug("Could not format date with locale %s: %s", locale_code, e)
        return date_obj.strftime("%B %d")


def get_localized_country_name(
    country_code: str, fallback_name: str | None = None
) -> str:
    """Get the English country name via Babel, e.g. "United States" for "US"."""
    try:
        from babel import Locale

        locale = Locale.parse(f"en_{country_code.upper()}")
        territory_name = locale.get_territory_name()
        if territory_name and territory_name != country_code.upper():
            return territory_name

    except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
        # Catches UnknownLocaleError, ValueError, AttributeError, etc.
        _LOGGER.debug(
            "Could not get localized name for country %s: %s", country_code, e
        )

    # Locale.parse("en_XX") can fail for territories the English locale still names.
    try:
        from babel import Locale

        en_locale = Locale("en")
        if country_code.upper() in en_locale.territories:
            return str(en_locale.territories[country_code.upper()])
    except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
        _LOGGER.debug("Could not look up territory name: %s", e)

    return fallback_name or country_code.replace("_", " ").title()


@lru_cache(maxsize=1)
def _get_holidays_module() -> ModuleType | None:
    """Import and cache the holidays module."""
    try:
        return importlib.import_module("holidays")
    except ImportError:
        _LOGGER.warning(
            "holidays library not available - holiday import feature disabled"
        )
        return None


def get_holidays_library_version() -> str | None:
    """Return the installed holidays library version, if available."""
    holidays_module = _get_holidays_module()
    if holidays_module is None:
        return None
    return getattr(holidays_module, "__version__", None)


def _build_holiday_cache_requests(
    schedules: Iterable[dict[str, Any]], years: Iterable[int]
) -> tuple[tuple[str, str | None, str, str, int], ...]:
    """Build unique holiday lookup requests for the supplied schedules."""
    unique_years = tuple(sorted({int(year) for year in years}))
    if not unique_years:
        return ()

    requests: set[tuple[str, str | None, str, str, int]] = set()

    for schedule in schedules:
        if schedule.get("schedule_type") != SCHEDULE_TYPE_HOLIDAY:
            continue

        try:
            country_code = str(schedule["country_code"]).upper()
            holiday_name = str(schedule["holiday_name"])
        except (KeyError, TypeError, ValueError):
            continue

        category_value = schedule.get("category")
        category = str(category_value) if category_value is not None else None
        lookup = str(schedule.get("name_lookup", "iexact"))

        for year in unique_years:
            requests.add((country_code, category, holiday_name, lookup, year))

    return tuple(
        sorted(
            requests,
            key=lambda item: (item[0], item[1] or "", item[2], item[3], item[4]),
        )
    )


def _prime_holiday_cache_sync(
    requests: tuple[tuple[str, str | None, str, str, int], ...],
) -> None:
    """Warm the holiday lookup cache for a set of named holiday requests."""
    for country_code, category, holiday_name, lookup, year in requests:
        try:
            _get_named_holiday_dates_sync(
                country_code, category, holiday_name, lookup, year
            )
        except Exception as err:  # noqa: BLE001 - cache priming must never fail the caller
            _LOGGER.warning(
                "Could not prime holiday cache for %s/%s %r in %s: %s",
                country_code,
                category or "public",
                holiday_name,
                year,
                err,
            )


async def async_prime_holiday_cache(
    schedules: Iterable[dict[str, Any]], years: Iterable[int]
) -> None:
    """Warm holiday lookup caches off the event loop for the supplied schedules."""
    requests = _build_holiday_cache_requests(schedules, years)
    if not requests:
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _prime_holiday_cache_sync, requests)


@lru_cache(maxsize=1024)
def _get_country_holidays_sync(
    country_code: str, category: str | None, year: int
) -> Any | None:
    """Return the holiday provider object for one country/category/year."""
    holidays_module = _get_holidays_module()
    if holidays_module is None:
        return None

    # The holidays library raises NotImplementedError for unknown countries and
    # ValueError for unsupported categories; both can occur for stored schedules
    # once a different library version is installed. One bad schedule must not
    # propagate and take down calendar setup or event listing for the rest.
    try:
        if category and category != "public":
            return holidays_module.country_holidays(
                country_code, categories=category, years=year
            )

        return holidays_module.country_holidays(country_code, years=year)
    except Exception as err:  # noqa: BLE001 - graceful fallback around third-party library quirks
        _LOGGER.warning(
            "Holiday provider rejected country %s (category %s) for %s: %s",
            country_code,
            category or "public",
            year,
            err,
        )
        return None


@lru_cache(maxsize=4096)
def _get_named_holiday_dates_sync(
    country_code: str,
    category: str | None,
    holiday_name: str,
    lookup: str,
    year: int,
) -> tuple[date, ...]:
    """Resolve dates for a named holiday in one year."""
    country_holidays = _get_country_holidays_sync(country_code, category, year)
    if country_holidays is None:
        return ()

    try:
        named_dates = country_holidays.get_named(holiday_name, lookup=lookup)
    except Exception as err:  # noqa: BLE001 - graceful fallback around third-party library quirks
        _LOGGER.debug(
            "Could not resolve holiday %s for %s/%s in %s: %s",
            holiday_name,
            country_code,
            category or "public",
            year,
            err,
        )
        return ()

    if not named_dates:
        # The holidays library may return names in a different language than the
        # stored holiday_name (e.g. English by default vs. the country's native
        # language). Retry with each supported language until a match is found.
        holidays_module = _get_holidays_module()
        supported_languages: tuple[str, ...] = getattr(
            country_holidays.__class__, "supported_languages", ()
        )
        default_language: str | None = getattr(
            country_holidays.__class__, "default_language", None
        )
        # Try default_language first, then the rest.
        languages_to_try = list(supported_languages)
        if default_language and default_language in languages_to_try:
            languages_to_try.remove(default_language)
            languages_to_try.insert(0, default_language)

        for lang in languages_to_try:
            # holidays_module cannot be None here (a provider object exists);
            # narrowed explicitly to satisfy the type checker.
            if (
                holidays_module is None
            ):  # pragma: no cover - unreachable without mutating the lru_cache mid-call; _get_holidays_module already returned non-None earlier in this call
                break
            try:
                kwargs: dict[str, Any] = {"years": year, "language": lang}
                if category and category != "public":
                    kwargs["categories"] = category
                lang_holidays = holidays_module.country_holidays(country_code, **kwargs)
                lang_dates = lang_holidays.get_named(holiday_name, lookup=lookup)
                if lang_dates:
                    named_dates = lang_dates
                    break
            except Exception as err:  # noqa: BLE001 - graceful fallback around third-party library quirks
                _LOGGER.debug("Language lookup failed for %s: %s", holiday_name, err)
                continue

    if not named_dates:
        if lookup != "icontains":
            # The library may have renamed the holiday since the schedule was
            # stored (e.g. "Thanksgiving" became "Thanksgiving Day" in v0.93).
            # Retry with a contains-style match before giving up.
            fallback_dates = _get_named_holiday_dates_sync(
                country_code, category, holiday_name, "icontains", year
            )
            if fallback_dates:
                _LOGGER.info(
                    "Holiday %r for %s/%s in %s only matched with a contains "
                    "lookup; the installed holidays library may have renamed it",
                    holiday_name,
                    country_code,
                    category or "public",
                    year,
                )
            return fallback_dates

        _LOGGER.warning(
            "Holiday %r could not be resolved for %s/%s in %s; the stored name "
            "may no longer exist in the installed holidays library",
            holiday_name,
            country_code,
            category or "public",
            year,
        )
        return ()

    return tuple(sorted(set(named_dates)))


def _merge_contiguous_dates(
    holiday_dates: tuple[date, ...] | list[date],
) -> list[tuple[date, date]]:
    """Collapse consecutive holiday dates into date ranges."""
    ordered_dates = sorted(set(holiday_dates))
    if not ordered_dates:
        return []

    ranges: list[tuple[date, date]] = []
    range_start = ordered_dates[0]
    range_end = ordered_dates[0]

    for holiday_date in ordered_dates[1:]:
        if holiday_date == range_end + timedelta(days=1):
            range_end = holiday_date
            continue

        ranges.append((range_start, range_end))
        range_start = holiday_date
        range_end = holiday_date

    ranges.append((range_start, range_end))
    return ranges


def _merge_overlapping_ranges(
    ranges: list[tuple[date, date]],
) -> list[tuple[date, date]]:
    """Merge overlapping or adjacent date ranges (input sorted by start).

    Offsets can make otherwise disjoint holiday occurrences overlap; a single
    schedule must never yield self-overlapping calendar events.
    """
    merged: list[tuple[date, date]] = []
    for range_start, range_end in ranges:
        if merged and range_start <= merged[-1][1] + timedelta(days=1):
            last_start, last_end = merged[-1]
            merged[-1] = (last_start, max(last_end, range_end))
        else:
            merged.append((range_start, range_end))
    return merged


def generate_holiday_schedule_dates(
    schedule: dict[str, Any], year: int
) -> list[tuple[date, date]]:
    """Generate date ranges for a holiday-backed schedule."""
    required_fields = ["country_code", "holiday_name"]
    if not all(schedule.get(field) for field in required_fields):
        return []

    try:
        country_code = str(schedule["country_code"]).upper()
        category = str(schedule.get("category", "public"))
        holiday_name = str(schedule["holiday_name"])
        lookup = str(schedule.get("name_lookup", "iexact"))
        start_offset = int(schedule.get("start_offset", 0))
        end_offset = int(schedule.get("end_offset", 0))
    except (TypeError, ValueError):
        return []

    holiday_dates = _get_named_holiday_dates_sync(
        country_code, category, holiday_name, lookup, year
    )
    if not holiday_dates:
        return []

    offset_ranges = [
        (
            range_start - timedelta(days=start_offset),
            range_end + timedelta(days=end_offset),
        )
        for range_start, range_end in _merge_contiguous_dates(holiday_dates)
    ]
    return _merge_overlapping_ranges(offset_ranges)


def build_holiday_schedule_pattern(
    country_code: str, category: str, holiday_name: str
) -> dict[str, Any]:
    """Build a holiday-backed pattern for import flows."""
    return {
        "schedule_type": SCHEDULE_TYPE_HOLIDAY,
        "country_code": country_code.upper(),
        "category": category,
        "holiday_name": holiday_name,
        "name_lookup": "iexact",
        "start_offset": 0,
        "end_offset": 0,
        "description": "Holiday-backed (resolved each year)",
    }


def _get_supported_countries_sync(today: date | None = None) -> dict[str, str]:
    """Get list of all supported countries dynamically (sync version).

    ``today`` anchors the sample year used to probe each country; defaults to
    the system date.
    """
    holidays_module = _get_holidays_module()
    if holidays_module is None:
        return {}

    sample_year = (today or date.today()).year

    try:
        country_dict = {}

        for country_code in holidays_module.list_supported_countries():
            try:
                country_obj = holidays_module.country_holidays(
                    country_code, years=sample_year
                )
                holidays_name = getattr(country_obj, "country", None)
                country_dict[country_code] = get_localized_country_name(
                    country_code, holidays_name
                )

            except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
                _LOGGER.debug("Could not get info for country %s: %s", country_code, e)
                continue

        return dict(sorted(country_dict.items(), key=lambda x: x[1]))

    except Exception:
        _LOGGER.exception("Failed to get supported countries")
        # Fallback to basic list if dynamic discovery fails
        return {
            "US": "United States",
            "CA": "Canada",
            "GB": "United Kingdom",
            "DE": "Germany",
            "FR": "France",
        }


async def get_supported_countries(today: date | None = None) -> dict[str, str]:
    """Get list of all supported countries dynamically."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_supported_countries_sync, today)


def _get_available_categories_sync(
    country_code: str, today: date | None = None
) -> dict[str, str]:
    """Get available holiday categories for a specific country (sync version).

    ``today`` anchors the sample year used to probe categories; defaults to
    the system date.
    """
    holidays_module = _get_holidays_module()
    if holidays_module is None:
        return {"public": "Public Holidays"}

    sample_year = (today or date.today()).year

    try:
        country_holidays = holidays_module.country_holidays(
            country_code, years=sample_year
        )

        available_categories = {
            category: category.replace("_", " ").title()
            for category in country_holidays.supported_categories
        }

        if not available_categories:
            available_categories = {"public": "Public Holidays"}

        return available_categories

    except Exception:
        _LOGGER.exception("Failed to get categories for %s", country_code)
        return {"public": "Public Holidays"}


async def get_available_categories(
    country_code: str, today: date | None = None
) -> dict[str, str]:
    """Get available holiday categories for a specific country."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _get_available_categories_sync, country_code, today
    )


def _get_holidays_for_country_sync(
    country_code: str,
    categories: list[str] | None = None,
    today: date | None = None,
) -> dict[str, dict[str, Any]]:
    """Get all holidays for a country with their patterns (sync version).

    ``today`` anchors the year window used for pattern analysis. Callers
    inside Home Assistant should pass ``dt_util.now().date()`` so the
    configured timezone is honored; defaults to the system date.
    """
    try:
        if categories is None:
            categories = list(
                _get_available_categories_sync(country_code, today).keys()
            )

        all_holidays: dict[str, dict[str, Any]] = {}

        # Get holidays for multiple years to analyze patterns
        today = today or date.today()
        years = list(
            range(
                today.year - CALENDAR_YEAR_LOOKAROUND,
                today.year + CALENDAR_YEAR_LOOKAROUND + 1,
            )
        )

        _LOGGER.debug(
            "Getting holidays for %s, categories: %s", country_code, categories
        )

        for category in categories:
            try:
                # Some countries might not support all categories
                for year in years:
                    try:
                        year_holidays = _get_country_holidays_sync(
                            country_code, category, year
                        )
                        if year_holidays is None:
                            continue

                        for holiday_date, holiday_name in year_holidays.items():
                            if holiday_name not in all_holidays:
                                all_holidays[holiday_name] = {
                                    "name": holiday_name,
                                    "category": category,
                                    "dates": [],
                                    "pattern": None,
                                }
                            all_holidays[holiday_name]["dates"].append(holiday_date)

                    except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
                        _LOGGER.debug(
                            "Could not get %s holidays for %s in %s: %s",
                            category,
                            country_code,
                            year,
                            e,
                        )
                        continue

            except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks  # pragma: no cover - unreachable short of a second failure inside the per-year except's own logging call, which already catches every Exception from the loop body
                _LOGGER.debug(
                    "Category %s not supported for %s: %s", category, country_code, e
                )
                continue

        # Analyze patterns for each holiday
        for holiday_name, holiday_data in all_holidays.items():
            if (
                holiday_data is None
            ):  # pragma: no cover - every value in all_holidays is a dict constructed above, never None
                _LOGGER.warning("Holiday data is None for %s", holiday_name)
                continue

            dates = holiday_data.get("dates", [])
            if not dates:  # pragma: no cover - each holiday entry is created together with an immediate dates.append() call
                _LOGGER.warning("No dates found for holiday %s", holiday_name)
                holiday_data["pattern"] = None
                continue

            pattern = analyze_holiday_pattern(dates)
            if (
                pattern is None
            ):  # pragma: no cover - dates is non-empty here, so analyze_holiday_pattern always returns a dict
                _LOGGER.warning(
                    "Could not analyze pattern for %s with dates %s",
                    holiday_name,
                    dates,
                )
                pattern = _build_fixed_date_pattern(
                    dates[0],
                    f"Single occurrence: {format_date_localized(dates[0])}",
                )
            elif pattern.get("variable_date"):
                pattern = build_holiday_schedule_pattern(
                    country_code, holiday_data["category"], holiday_name
                )

            holiday_data["pattern"] = pattern

        return all_holidays

    except Exception:
        _LOGGER.exception("Failed to get holidays for %s", country_code)
        return {}


async def get_holidays_for_country(
    country_code: str,
    categories: list[str] | None = None,
    today: date | None = None,
) -> dict[str, dict[str, Any]]:
    """Get all holidays for a country with their patterns.

    ``today`` anchors the year window used for pattern analysis; see
    ``_get_holidays_for_country_sync``.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _get_holidays_for_country_sync, country_code, categories, today
    )


def _build_fixed_date_pattern(
    date_obj: date, description: str, *, variable_date: bool = False
) -> dict[str, Any]:
    """Build a single-day date pattern anchored on ``date_obj``."""
    pattern: dict[str, Any] = {
        "schedule_type": SCHEDULE_TYPE_DATE,
        "start_month": date_obj.month,
        "start_day": date_obj.day,
        "end_month": date_obj.month,
        "end_day": date_obj.day,
        "description": description,
    }
    if variable_date:
        pattern["variable_date"] = True
    return pattern


def analyze_holiday_pattern(dates: list[date]) -> dict[str, Any] | None:
    """Analyze holiday dates to determine schedule pattern."""
    if len(dates) < 1:
        return None

    dates.sort()

    # Same month/day every year (e.g. July 4th), or just one date
    if all(d.month == dates[0].month and d.day == dates[0].day for d in dates):
        return _build_fixed_date_pattern(
            dates[0], f"Fixed date: {format_date_localized(dates[0])}"
        )

    first_date = dates[0]

    # Group dates by year for recurrence analysis
    dates_by_year: dict[int, list[date]] = {}
    for d in dates:
        dates_by_year.setdefault(d.year, []).append(d)

    # Single date per year, same month and weekday: nth weekday of month.
    # The occurrence is validated by regenerating every input year rather
    # than trusting the first year alone (a 4th weekday that happens to be
    # last in one year must not turn the whole pattern into "last").
    if (
        len(dates_by_year) >= 2
        and all(len(year_dates) == 1 for year_dates in dates_by_year.values())
        and all(
            d.month == first_date.month and d.weekday() == first_date.weekday()
            for d in dates
        )
    ):
        pattern = _build_nth_weekday_pattern(dates, span_days=0)
        if pattern:
            return pattern

    # Multi-day holidays: fixed-length span anchored on an nth weekday
    if span_pattern := _analyze_multi_day_pattern(dates_by_year):
        return span_pattern

    return _build_fixed_date_pattern(
        first_date,
        f"Variable date (using {first_date.year} date: {format_date_localized(first_date)})",
        variable_date=True,
    )


def _build_nth_weekday_pattern(
    anchor_dates: list[date], span_days: int
) -> dict[str, Any] | None:
    """Build an nth-day pattern that regenerates every anchor date exactly.

    Returns the pattern for the first occurrence value (0-4, 4 = last) that
    reproduces all anchors via ``_get_nth_weekday``, or ``None`` when the
    anchors do not share a single consistent occurrence.
    """
    from .schedule_generator import _get_nth_weekday

    first = anchor_dates[0]
    month = first.month
    day_of_week = first.weekday()

    for occurrence in range(len(OCCURRENCE_NAMES_DISPLAY)):
        if all(
            _get_nth_weekday(d.year, month, occurrence, day_of_week) == d
            for d in anchor_dates
        ):
            description = (
                f"{OCCURRENCE_NAMES_DISPLAY[occurrence]} "
                f"{DAY_NAMES_DISPLAY[day_of_week]} of {MONTH_NAMES_DISPLAY[month]}"
            )
            if span_days:
                description += f" ({span_days + 1} days)"
            return {
                "schedule_type": SCHEDULE_TYPE_NTH_DAY,
                "month": month,
                "occurrence": occurrence,
                "day_of_week": day_of_week,
                "start_offset": 0,
                "end_offset": span_days,
                "description": description,
            }

    return None


def _analyze_multi_day_pattern(
    dates_by_year: dict[int, list[date]],
) -> dict[str, Any] | None:
    """Detect fixed-length multi-day spans anchored on an nth weekday.

    Emits an nth-day schedule with ``end_offset`` covering the span. This
    replaces the former week-based patterns, whose stored week numbers were
    weekday occurrences while the generator expected calendar weeks — such
    schedules generated events in almost no years.
    """
    if len(dates_by_year) < 2:
        return None

    anchors: list[date] = []
    spans: set[int] = set()

    for _year, year_dates in sorted(dates_by_year.items()):
        year_dates.sort()
        first, last = year_dates[0], year_dates[-1]
        span = (last - first).days
        # Only short spans fully contained in one month qualify; anything
        # else is safer represented as a holiday-backed schedule.
        if len(year_dates) < 2 or first.month != last.month or not 1 <= span <= 6:
            return None
        anchors.append(first)
        spans.add(span)

    if len(spans) != 1:
        return None
    if len({anchor.month for anchor in anchors}) != 1:
        return None
    if len({anchor.weekday() for anchor in anchors}) != 1:
        return None

    return _build_nth_weekday_pattern(anchors, span_days=spans.pop())
