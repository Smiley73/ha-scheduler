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

# Babel imports moved inside functions to avoid blocking I/O during module import

_LOGGER = logging.getLogger(__name__)


def format_date_localized(date_obj: date, locale_code: str | None = None) -> str:
    """Format a date using locale-aware formatting.

    Args:
        date_obj: Date to format
        locale_code: Optional locale code (e.g., 'en_US'). Defaults to 'en'.

    Returns:
        Formatted date string like "January 1" or "December 25"
    """
    try:
        # Lazy import to avoid blocking I/O during module import
        from babel import Locale
        from babel.dates import format_date

        # Use provided locale or default to English
        locale = Locale.parse(locale_code or "en")
        # Format as "Month Day" (e.g., "January 1", "December 25")
        return format_date(date_obj, format="MMMM d", locale=locale)
    except ImportError as e:
        _LOGGER.debug("Babel not available for date formatting: %s", e)
        # Fallback to Python's strftime
        return date_obj.strftime("%B %d")
    except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
        # Catches UnknownLocaleError, ValueError, etc.
        _LOGGER.debug("Could not format date with locale %s: %s", locale_code, e)
        # Fallback to Python's strftime
        return date_obj.strftime("%B %d")


def get_localized_country_name(
    country_code: str, fallback_name: str | None = None
) -> str:
    """Get localized country name using Babel.

    Args:
        country_code: ISO 3166-1 alpha-2 country code
        fallback_name: Fallback name if Babel lookup fails

    Returns:
        Localized country name or fallback
    """
    try:
        # Lazy import to avoid blocking I/O during module import
        from babel import Locale

        # Create a locale for the country to get its display name
        locale = Locale.parse(f"en_{country_code.upper()}")

        # Get the territory display name in English
        # This provides proper country names like "United States" instead of "US"
        territory_name = locale.get_territory_name()
        if territory_name and territory_name != country_code.upper():
            return territory_name

    except ImportError as e:
        _LOGGER.debug("Babel not available for country names: %s", e)
        return fallback_name or country_code.replace("_", " ").title()
    except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
        # Catches UnknownLocaleError, ValueError, AttributeError, etc.
        _LOGGER.debug(
            "Could not get localized name for country %s: %s", country_code, e
        )

    # Try using Babel's territory data from English locale
    try:
        from babel import Locale

        en_locale = Locale("en")
        if country_code.upper() in en_locale.territories:
            return str(en_locale.territories[country_code.upper()])
    except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
        # Any error including ImportError
        _LOGGER.debug("Could not look up territory name: %s", e)

    # Fallback to provided name or formatted country code
    return fallback_name or country_code.replace("_", " ").title()


# Test override for holiday library availability. Runtime code leaves this as
# None so the actual import is deferred until a sync helper runs in the executor.
HOLIDAYS_AVAILABLE: bool | None = None


@lru_cache(maxsize=1)
def _get_holidays_module() -> ModuleType | None:
    """Import and cache the holidays module."""
    try:
        return importlib.import_module("holidays")
    except ImportError:
        return None


def _holidays_available() -> bool:
    """Return whether the holidays library is available."""
    global HOLIDAYS_AVAILABLE

    if HOLIDAYS_AVAILABLE is None:
        HOLIDAYS_AVAILABLE = _get_holidays_module() is not None
        if not HOLIDAYS_AVAILABLE:
            _LOGGER.warning(
                "holidays library not available - holiday import feature disabled"
            )

    return HOLIDAYS_AVAILABLE


def get_holidays_library_version() -> str | None:
    """Return the installed holidays library version, if available."""
    holidays_module = _get_holidays_module()
    if holidays_module is None:
        return None
    return getattr(holidays_module, "__version__", None)


def _clear_holiday_caches() -> None:
    """Clear cached holiday metadata for tests."""
    global HOLIDAYS_AVAILABLE

    HOLIDAYS_AVAILABLE = None
    _get_holidays_module.cache_clear()
    _get_country_holidays_sync.cache_clear()
    _get_named_holiday_dates_sync.cache_clear()


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
    if not _holidays_available():
        return None

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
        if hasattr(country_holidays, "get_named"):
            named_dates = country_holidays.get_named(holiday_name, lookup=lookup)
        else:
            named_dates = [
                holiday_date
                for holiday_date, current_name in country_holidays.items()
                if str(current_name).casefold() == holiday_name.casefold()
            ]
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
            # holidays_module cannot be None here (a provider object exists),
            # but narrow explicitly to satisfy the type checker and mirror the
            # defensive checks elsewhere in this file.
            if (
                holidays_module is None
            ):  # pragma: no cover - unreachable without mutating the lru_cache mid-call; _get_holidays_module already returned non-None earlier in this call
                break
            try:
                kwargs: dict[str, Any] = {"years": year, "language": lang}
                if category and category != "public":
                    kwargs["categories"] = category
                lang_holidays = holidays_module.country_holidays(country_code, **kwargs)
                if hasattr(lang_holidays, "get_named"):
                    lang_dates = lang_holidays.get_named(holiday_name, lookup=lookup)
                else:
                    lang_dates = [
                        holiday_date
                        for holiday_date, current_name in lang_holidays.items()
                        if str(current_name).casefold() == holiday_name.casefold()
                    ]
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


def _should_use_holiday_schedule_pattern(pattern: dict[str, Any] | None) -> bool:
    """Return whether a detected pattern should use the holiday schedule type."""
    if pattern is None:
        return False

    return bool(pattern.get("variable_date"))


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
    if not _holidays_available():
        return {}

    holidays_module = _get_holidays_module()
    if holidays_module is None:
        return {}

    sample_year = (today or date.today()).year

    try:
        # Get all available countries from holidays library
        country_dict = {}

        # holidays library provides country codes and names
        for country_code in holidays_module.list_supported_countries():
            try:
                # Get the country name from holidays library first
                country_obj = holidays_module.country_holidays(
                    country_code, years=sample_year
                )
                holidays_name = getattr(country_obj, "country", None)

                # If holidays library doesn't have a proper name, try the class
                if not holidays_name or holidays_name == country_code:
                    try:
                        # Access the entity loader and get the country class
                        entity_loader = getattr(
                            holidays_module.registry, "EntityLoader", None
                        )
                        if entity_loader and hasattr(entity_loader, "get"):
                            country_class = entity_loader.get(country_code)
                            if hasattr(country_class, "country"):
                                holidays_name = country_class.country
                    except (AttributeError, KeyError, ImportError, TypeError):
                        pass

                # Use Babel to get the proper localized country name
                # This provides better names than the holidays library fallbacks
                country_name = get_localized_country_name(country_code, holidays_name)
                country_dict[country_code] = country_name

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
    if not _holidays_available():
        return {"public": "Public Holidays"}

    holidays_module = _get_holidays_module()
    if holidays_module is None:
        return {"public": "Public Holidays"}

    sample_year = (today or date.today()).year

    try:
        # Get a sample year to inspect available categories
        country_holidays = holidays_module.country_holidays(
            country_code, years=sample_year
        )

        # Different countries support different categories
        available_categories = {}

        # Check what categories this country supports
        if hasattr(country_holidays, "supported_categories"):
            for category in country_holidays.supported_categories:
                # Convert category code to readable name
                category_name = category.replace("_", " ").title()
                available_categories[category] = category_name
        else:
            # Try common categories and see which ones work
            test_categories = [
                "public",
                "bank",
                "school",
                "optional",
                "observance",
                "government",
                "financial",
            ]

            for category in test_categories:
                try:
                    # Test if this category exists by trying to create holidays with it
                    test_holidays = holidays_module.country_holidays(
                        country_code, categories=category, years=sample_year
                    )
                    if len(test_holidays) > 0:
                        category_name = category.replace("_", " ").title()
                        available_categories[category] = category_name
                except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
                    _LOGGER.debug(
                        "Category %s not supported for %s: %s",
                        category,
                        country_code,
                        e,
                    )
                    continue

        # If no categories found, default to 'public'
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
    if not _holidays_available():
        return {}

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

            except Exception as e:  # noqa: BLE001 - graceful fallback around third-party library quirks
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
                # Create a fallback pattern using the first date
                if dates:
                    first_date = dates[0]
                    pattern = {
                        "schedule_type": SCHEDULE_TYPE_DATE,
                        "start_month": first_date.month,
                        "start_day": first_date.day,
                        "end_month": first_date.month,
                        "end_day": first_date.day,
                        "description": f"Single occurrence: {format_date_localized(first_date)}",
                    }
            elif _should_use_holiday_schedule_pattern(pattern):
                pattern = build_holiday_schedule_pattern(
                    country_code, category, holiday_name
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


def analyze_holiday_pattern(dates: list[date]) -> dict[str, Any] | None:
    """Analyze holiday dates to determine schedule pattern."""
    if len(dates) < 1:
        return None

    # If we only have one date, create a fixed date pattern
    if len(dates) == 1:
        date_obj = dates[0]
        return {
            "schedule_type": SCHEDULE_TYPE_DATE,
            "start_month": date_obj.month,
            "start_day": date_obj.day,
            "end_month": date_obj.month,
            "end_day": date_obj.day,
            "description": f"Fixed date: {format_date_localized(date_obj)}",
        }

    # Sort dates to analyze pattern
    dates.sort()

    # Check if it's a fixed date (same month/day every year)
    if all(d.month == dates[0].month and d.day == dates[0].day for d in dates):
        # Fixed date pattern (e.g., July 4th, Christmas)
        return {
            "schedule_type": SCHEDULE_TYPE_DATE,
            "start_month": dates[0].month,
            "start_day": dates[0].day,
            "end_month": dates[0].month,
            "end_day": dates[0].day,
            "description": f"Fixed date: {format_date_localized(dates[0])}",
        }

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

    # If we can't determine a clear pattern, default to first occurrence as date
    return {
        "schedule_type": SCHEDULE_TYPE_DATE,
        "start_month": first_date.month,
        "start_day": first_date.day,
        "end_month": first_date.month,
        "end_day": first_date.day,
        "variable_date": True,
        "description": f"Variable date (using {first_date.year} date: {format_date_localized(first_date)})",
    }


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


def calculate_occurrence(target_date: date) -> int | None:
    """Calculate which occurrence of weekday in month (0-4, where 4=last)."""
    try:
        year = target_date.year
        month = target_date.month
        day_of_week = target_date.weekday()

        # Find all occurrences of this weekday in the month
        first_day = date(year, month, 1)

        # Calculate days until first occurrence of this weekday
        days_until_first = (day_of_week - first_day.weekday()) % 7
        first_occurrence = first_day + timedelta(days=days_until_first)

        # Calculate which occurrence this date is
        occurrence = (target_date - first_occurrence).days // 7

        # Check if it's the last occurrence
        try:
            next_occurrence = first_occurrence + timedelta(weeks=occurrence + 1)
            if next_occurrence.month != month:
                # This is the last occurrence
                return 4
        except (ValueError, OverflowError) as e:
            _LOGGER.debug("Could not calculate next occurrence: %s", e)
            return 4

        return occurrence

    except Exception:  # noqa: BLE001 - graceful fallback around third-party library quirks
        return None
