"""Holiday schedule importer for HA Scheduler."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

_LOGGER = logging.getLogger(__name__)

try:
    import holidays

    HOLIDAYS_AVAILABLE = True
except ImportError:
    HOLIDAYS_AVAILABLE = False
    _LOGGER.warning("holidays library not available - holiday import feature disabled")


def _get_supported_countries_sync() -> dict[str, str]:
    """Get list of all supported countries dynamically (sync version)."""
    if not HOLIDAYS_AVAILABLE:
        return {}

    try:
        # Get all available countries from holidays library
        country_dict = {}

        # holidays library provides country codes and names
        for country_code in holidays.list_supported_countries():
            try:
                # Get the country name - some countries may have display names
                country_obj = holidays.country_holidays(country_code, years=2024)
                country_name = getattr(country_obj, "country", country_code)

                # If no proper name, try to get it from the class
                if country_name == country_code:
                    try:
                        country_class = holidays.registry.EntityLoader.get(country_code)
                        if hasattr(country_class, "country"):
                            country_name = country_class.country
                        else:
                            # Fallback to a readable format
                            country_name = country_code.replace("_", " ").title()
                    except (AttributeError, KeyError, ImportError) as e:
                        _LOGGER.debug(
                            "Could not get country name for %s: %s", country_code, e
                        )
                        country_name = country_code.replace("_", " ").title()

                country_dict[country_code] = country_name

            except Exception as e:
                _LOGGER.debug("Could not get info for country %s: %s", country_code, e)
                continue

        return dict(sorted(country_dict.items(), key=lambda x: x[1]))

    except Exception as e:
        _LOGGER.error("Failed to get supported countries: %s", e)
        # Fallback to basic list if dynamic discovery fails
        return {
            "US": "United States",
            "CA": "Canada",
            "GB": "United Kingdom",
            "DE": "Germany",
            "FR": "France",
        }


async def get_supported_countries() -> dict[str, str]:
    """Get list of all supported countries dynamically."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_supported_countries_sync)


def _get_available_categories_sync(country_code: str) -> dict[str, str]:
    """Get available holiday categories for a specific country (sync version)."""
    if not HOLIDAYS_AVAILABLE:
        return {"public": "Public Holidays"}

    try:
        # Get a sample year to inspect available categories
        country_holidays = holidays.country_holidays(country_code, years=2024)

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
                    test_holidays = holidays.country_holidays(
                        country_code, categories=category, years=2024
                    )
                    if len(test_holidays) > 0:
                        category_name = category.replace("_", " ").title()
                        available_categories[category] = category_name
                except Exception as e:
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

    except Exception as e:
        _LOGGER.error("Failed to get categories for %s: %s", country_code, e)
        return {"public": "Public Holidays"}


async def get_available_categories(country_code: str) -> dict[str, str]:
    """Get available holiday categories for a specific country."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _get_available_categories_sync, country_code
    )


def _get_holidays_for_country_sync(
    country_code: str, categories: list[str] = None
) -> dict[str, dict[str, Any]]:
    """Get all holidays for a country with their patterns (sync version)."""
    if not HOLIDAYS_AVAILABLE:
        return {}

    try:
        if categories is None:
            categories = list(_get_available_categories_sync(country_code).keys())

        all_holidays = {}

        # Get holidays for multiple years to analyze patterns
        years = [2023, 2024, 2025]

        _LOGGER.debug(
            "Getting holidays for %s, categories: %s", country_code, categories
        )

        for category in categories:
            try:
                # Some countries might not support all categories
                for year in years:
                    try:
                        if category == "public":
                            # Default category - no category parameter needed
                            year_holidays = holidays.country_holidays(
                                country_code, years=year
                            )
                        else:
                            # Specific category
                            year_holidays = holidays.country_holidays(
                                country_code, categories=category, years=year
                            )

                        for holiday_date, holiday_name in year_holidays.items():
                            if holiday_name not in all_holidays:
                                all_holidays[holiday_name] = {
                                    "name": holiday_name,
                                    "category": category,
                                    "dates": [],
                                    "pattern": None,
                                }
                            all_holidays[holiday_name]["dates"].append(holiday_date)

                    except Exception as e:
                        _LOGGER.debug(
                            "Could not get %s holidays for %s in %s: %s",
                            category,
                            country_code,
                            year,
                            e,
                        )
                        continue

            except Exception as e:
                _LOGGER.debug(
                    "Category %s not supported for %s: %s", category, country_code, e
                )
                continue

        # Analyze patterns for each holiday
        for holiday_name, holiday_data in all_holidays.items():
            if holiday_data is None:
                _LOGGER.warning("Holiday data is None for %s", holiday_name)
                continue

            dates = holiday_data.get("dates", [])
            if not dates:
                _LOGGER.warning("No dates found for holiday %s", holiday_name)
                holiday_data["pattern"] = None
                continue

            pattern = analyze_holiday_pattern(dates)
            if pattern is None:
                _LOGGER.warning(
                    "Could not analyze pattern for %s with dates %s",
                    holiday_name,
                    dates,
                )
                # Create a fallback pattern using the first date
                if dates:
                    first_date = dates[0]
                    pattern = {
                        "schedule_type": "date",
                        "start_month": first_date.month,
                        "start_day": first_date.day,
                        "end_month": first_date.month,
                        "end_day": first_date.day,
                        "description": f"Single occurrence: {first_date.strftime('%B %d')}",
                    }

            holiday_data["pattern"] = pattern

        return all_holidays

    except Exception as e:
        _LOGGER.error("Failed to get holidays for %s: %s", country_code, e)
        return {}


async def get_holidays_for_country(
    country_code: str, categories: list[str] = None
) -> dict[str, dict[str, Any]]:
    """Get all holidays for a country with their patterns."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _get_holidays_for_country_sync, country_code, categories
    )


def analyze_holiday_pattern(dates: list[date]) -> dict[str, Any] | None:
    """Analyze holiday dates to determine schedule pattern."""
    if len(dates) < 1:
        return None

    # If we only have one date, create a fixed date pattern
    if len(dates) == 1:
        date_obj = dates[0]
        return {
            "schedule_type": "date",
            "start_month": date_obj.month,
            "start_day": date_obj.day,
            "end_month": date_obj.month,
            "end_day": date_obj.day,
            "description": f"Fixed date: {date_obj.strftime('%B %d')}",
        }

    # Sort dates to analyze pattern
    dates.sort()

    # Check if it's a fixed date (same month/day every year)
    if all(d.month == dates[0].month and d.day == dates[0].day for d in dates):
        # Fixed date pattern (e.g., July 4th, Christmas)
        return {
            "schedule_type": "date",
            "start_month": dates[0].month,
            "start_day": dates[0].day,
            "end_month": dates[0].month,
            "end_day": dates[0].day,
            "description": f"Fixed date: {dates[0].strftime('%B %d')}",
        }
    else:
        # Variable date - try to determine pattern
        first_date = dates[0]

        # Check if all dates are in the same month and same weekday
        if all(
            d.month == first_date.month and d.weekday() == first_date.weekday()
            for d in dates
        ):
            month = first_date.month
            day_of_week = first_date.weekday()

            # Calculate which occurrence (1st, 2nd, 3rd, 4th, or last)
            occurrence = calculate_occurrence(first_date)

            if occurrence is not None:
                occurrence_names = ["First", "Second", "Third", "Fourth", "Last"]
                day_names = [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
                month_names = [
                    "",
                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December",
                ]

                # Check if this could be a week-based pattern instead
                # Some holidays might span multiple days in the same week
                week_pattern = _analyze_week_pattern(dates)
                if week_pattern:
                    return week_pattern

                return {
                    "schedule_type": "nth-day",
                    "month": month,
                    "occurrence": occurrence,
                    "day_of_week": day_of_week,
                    "start_offset": 0,
                    "end_offset": 0,
                    "description": f"{occurrence_names[occurrence]} {day_names[day_of_week]} of {month_names[month]}",
                }

        # Check for week-based patterns (holidays that span multiple days)
        week_pattern = _analyze_week_pattern(dates)
        if week_pattern:
            return week_pattern

        # If we can't determine a clear pattern, default to first occurrence as date
        return {
            "schedule_type": "date",
            "start_month": first_date.month,
            "start_day": first_date.day,
            "end_month": first_date.month,
            "end_day": first_date.day,
            "description": f"Variable date (using {first_date.year} date: {first_date.strftime('%B %d')})",
        }


def _analyze_week_pattern(dates: list[date]) -> dict[str, Any] | None:
    """Analyze if dates follow a week-based pattern."""
    if len(dates) < 2:
        return None

    # Group dates by year to analyze patterns
    dates_by_year = {}
    for d in dates:
        if d.year not in dates_by_year:
            dates_by_year[d.year] = []
        dates_by_year[d.year].append(d)

    # Check if we have consistent patterns across years
    if len(dates_by_year) < 2:
        return None

    # Look for patterns where dates span multiple consecutive days in the same week/month
    for year, year_dates in dates_by_year.items():
        year_dates.sort()

        # Check if dates are consecutive and in the same month
        if len(year_dates) >= 2:
            first_date = year_dates[0]
            last_date = year_dates[-1]

            # Check if they're in the same month and span multiple days
            if (
                first_date.month == last_date.month
                and (last_date - first_date).days >= 1
                and (last_date - first_date).days <= 6
            ):  # Within a week
                # Try to determine if this follows a week pattern
                start_occurrence = calculate_occurrence(first_date)
                end_occurrence = calculate_occurrence(last_date)

                if start_occurrence is not None and end_occurrence is not None:
                    # Check if this pattern is consistent across other years
                    consistent = True
                    for other_year, other_dates in dates_by_year.items():
                        if other_year == year:
                            continue

                        other_dates.sort()
                        if len(other_dates) >= 2:
                            other_first = other_dates[0]
                            other_last = other_dates[-1]

                            other_start_occ = calculate_occurrence(other_first)
                            other_end_occ = calculate_occurrence(other_last)

                            if (
                                other_first.month != first_date.month
                                or other_start_occ != start_occurrence
                                or other_end_occ != end_occurrence
                                or other_first.weekday() != first_date.weekday()
                                or other_last.weekday() != last_date.weekday()
                            ):
                                consistent = False
                                break

                    if consistent:
                        occurrence_names = [
                            "First",
                            "Second",
                            "Third",
                            "Fourth",
                            "Last",
                        ]
                        day_names = [
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                            "Saturday",
                            "Sunday",
                        ]
                        month_names = [
                            "",
                            "January",
                            "February",
                            "March",
                            "April",
                            "May",
                            "June",
                            "July",
                            "August",
                            "September",
                            "October",
                            "November",
                            "December",
                        ]

                        # Create week-based schedule with appropriate week types
                        schedule = {
                            "schedule_type": "week",
                            "start_month": first_date.month,
                            "start_week": start_occurrence,
                            "start_day_of_week": first_date.weekday(),
                            "end_month": last_date.month,
                            "end_week": end_occurrence,
                            "end_day_of_week": last_date.weekday(),
                        }

                        # Add week types for first weeks (occurrence 0)
                        # Default to "partial" for holidays as they typically follow calendar weeks
                        if start_occurrence == 0:
                            schedule["start_week_type"] = "partial"
                        if end_occurrence == 0:
                            schedule["end_week_type"] = "partial"

                        if start_occurrence == end_occurrence:
                            # Same week, different days
                            schedule["description"] = (
                                f"{occurrence_names[start_occurrence]} week of {month_names[first_date.month]} ({day_names[first_date.weekday()]} to {day_names[last_date.weekday()]})"
                            )
                        else:
                            # Different weeks
                            schedule["description"] = (
                                f"{occurrence_names[start_occurrence]} {day_names[first_date.weekday()]} to {occurrence_names[end_occurrence]} {day_names[last_date.weekday()]} of {month_names[first_date.month]}"
                            )

                        return schedule

    return None


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

    except Exception:
        return None
