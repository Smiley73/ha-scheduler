"""Diagnostics support for Scheduler."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DAY_NAMES,
    SCHEDULE_TYPE_DATE,
    SCHEDULE_TYPE_HOLIDAY,
    SCHEDULE_TYPE_NTH_DAY,
    SCHEDULE_TYPE_WEEK,
)
from .holiday_importer import async_prime_holiday_cache
from .schedule_generator import generate_schedule_dates

# Keys that may contain sensitive user data in YAML configuration blobs
_REDACT_KEYS = frozenset(
    {
        "api_key",
        "api_token",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "key",
        "authorization",
        "credential",
    }
)

_LOGGER = logging.getLogger(__name__)


def _get_day_name(day_of_week: int | None) -> str | None:
    """Convert day of week number to day name.

    Args:
        day_of_week: Day number (0=Monday, 1=Tuesday, ..., 6=Sunday)

    Returns:
        Day name or None if invalid
    """
    if day_of_week is None or not (0 <= day_of_week <= 6):
        return None
    return DAY_NAMES[day_of_week].capitalize()


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # Handle both new service-based structure and legacy structure
    services = entry.options.get("services", {})

    if not services:
        # Legacy structure - create a default service
        legacy_schedules = entry.options.get("schedules", {})
        legacy_config = entry.options.get("configuration", {})
        services = {
            "default": {
                "name": entry.title,
                "schedules": legacy_schedules,
                "configuration": legacy_config,
            }
        }

    current_year = dt_util.now().date().year
    all_schedules = [
        schedule
        for service_data in services.values()
        for schedule in service_data.get("schedules", {}).values()
    ]
    await async_prime_holiday_cache(
        all_schedules, range(current_year, current_year + 3)
    )

    # Collect diagnostics for all services
    services_diagnostics = {}
    total_schedules = 0

    for service_id, service_data in services.items():
        schedules = service_data.get("schedules", {})
        service_config = service_data.get("configuration", {})
        total_schedules += len(schedules)

        # Build schedule summary for this service
        schedule_summary = []
        for schedule_id, schedule_data in schedules.items():
            schedule_info = _build_schedule_info(schedule_data, schedule_id, schedules)
            schedule_summary.append(schedule_info)

        services_diagnostics[service_id] = {
            "name": service_data.get("name", "Unknown"),
            "schedules": {
                "count": len(schedules),
                "items": schedule_summary,
            },
            "default_configuration": {
                "has_configuration": bool(service_config),
                "configuration": async_redact_data(service_config, _REDACT_KEYS)
                if service_config
                else None,
            },
        }

    return {
        "entry": {
            "title": entry.title,
            "entry_id": entry.entry_id,
            "scheduler_name": entry.data.get("scheduler_name", entry.title),
        },
        "services": services_diagnostics,
        "summary": {
            "total_services": len(services),
            "total_schedules": total_schedules,
        },
    }


def _build_schedule_info(
    schedule_data: dict[str, Any], schedule_id: str, all_schedules: dict[str, Any]
) -> dict[str, Any]:
    """Build diagnostic information for a single schedule."""
    schedule_info = {
        "id": schedule_id,
        "name": schedule_data.get("name"),
        "type": schedule_data.get("schedule_type"),
    }

    # Add type-specific fields
    if schedule_data.get("schedule_type") == SCHEDULE_TYPE_DATE:
        schedule_info.update(
            {
                "start_month": schedule_data.get("start_month"),
                "start_day": schedule_data.get("start_day"),
                "end_month": schedule_data.get("end_month"),
                "end_day": schedule_data.get("end_day"),
            }
        )
    elif schedule_data.get("schedule_type") == SCHEDULE_TYPE_WEEK:
        start_day_of_week = schedule_data.get("start_day_of_week")
        end_day_of_week = schedule_data.get("end_day_of_week")
        start_week_type = schedule_data.get("start_week_type", "partial")
        end_week_type = schedule_data.get("end_week_type", "partial")

        def _get_week_type_display(week_type: str) -> str:
            return (
                "First full week (entirely within month)"
                if week_type == "full"
                else "First week (may start in previous month)"
            )

        schedule_info.update(
            {
                "start_month": schedule_data.get("start_month"),
                "start_week": schedule_data.get("start_week"),
                "start_week_type": start_week_type,
                "start_week_type_display": _get_week_type_display(start_week_type),
                "start_day_of_week": start_day_of_week,
                "start_day_name": _get_day_name(start_day_of_week)
                if start_day_of_week is not None
                else "Whole week",
                "end_month": schedule_data.get("end_month"),
                "end_week": schedule_data.get("end_week"),
                "end_week_type": end_week_type,
                "end_week_type_display": _get_week_type_display(end_week_type),
                "end_day_of_week": end_day_of_week,
                "end_day_name": _get_day_name(end_day_of_week)
                if end_day_of_week is not None
                else "Whole week",
                "country_code": schedule_data.get("country_code"),
            }
        )
    elif schedule_data.get("schedule_type") == SCHEDULE_TYPE_NTH_DAY:
        day_of_week = schedule_data.get("day_of_week")
        schedule_info.update(
            {
                "month": schedule_data.get("month"),
                "occurrence": schedule_data.get("occurrence"),
                "day_of_week": day_of_week,
                "day_name": _get_day_name(day_of_week),
                "start_offset": schedule_data.get("start_offset"),
                "end_offset": schedule_data.get("end_offset"),
            }
        )
    elif schedule_data.get("schedule_type") == SCHEDULE_TYPE_HOLIDAY:
        schedule_info.update(
            {
                "country_code": schedule_data.get("country_code"),
                "category": schedule_data.get("category"),
                "holiday_name": schedule_data.get("holiday_name"),
                "name_lookup": schedule_data.get("name_lookup"),
                "start_offset": schedule_data.get("start_offset"),
                "end_offset": schedule_data.get("end_offset"),
            }
        )

    # Include configuration if present (redact sensitive keys)
    if "configuration" in schedule_data:
        schedule_info["has_configuration"] = True
        schedule_info["configuration"] = async_redact_data(
            schedule_data["configuration"], _REDACT_KEYS
        )
    else:
        schedule_info["has_configuration"] = False

    # Add schedule dates and durations for next 3 years
    schedule_info["future_dates"] = _calculate_future_dates(
        schedule_data, all_schedules, schedule_id
    )

    return schedule_info


def _calculate_future_dates(
    schedule_data: dict[str, Any],
    all_schedules: dict[str, Any],
    current_schedule_id: str,
) -> dict[str, Any]:
    """Calculate schedule dates and durations for the next 3 years.

    Also checks for overlaps with other schedules for each year.

    Args:
        schedule_data: The current schedule data
        all_schedules: All schedules in the config entry
        current_schedule_id: ID of the current schedule to exclude from overlap checks

    Returns:
        Dictionary with yearly data, overlap information, and any computation warnings.
    """
    current_year = dt_util.now().date().year
    future_data: dict[str, Any] = {"years": {}, "warnings": []}

    for year in range(current_year, current_year + 3):
        year_key = str(year)
        try:
            date_ranges = generate_schedule_dates(schedule_data, year)

            if not date_ranges:
                warnings_list: list[str] = future_data["warnings"]
                warnings_list.append(f"No valid dates generated for year {year}")
                years_dict: dict[str, Any] = future_data["years"]
                years_dict[year_key] = {
                    "error": "No valid dates generated",
                    "start_date": None,
                    "end_date": None,
                    "duration_days": None,
                }
                continue

            # Take the first date range (most schedules have only one per year)
            start_date, end_date = date_ranges[0]

            # Calculate duration in days
            duration = (
                end_date - start_date
            ).days + 1  # +1 to include both start and end days

            # Check for overlaps with other schedules in this specific year
            overlaps = _check_year_overlaps(
                schedule_data, all_schedules, current_schedule_id, year
            )

            years_dict_main: dict[str, Any] = future_data["years"]
            years_dict_main[year_key] = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "duration_days": duration,
                "overlaps": overlaps,
            }

        except Exception as e:  # noqa: BLE001 - diagnostics must never fail; error is recorded in output
            _LOGGER.warning(
                "Failed to calculate schedule dates for year %s: %s", year, str(e)
            )
            warnings_list_err: list[str] = future_data["warnings"]
            warnings_list_err.append(f"Failed to compute dates for year {year}: {e!s}")
            years_dict_err: dict[str, Any] = future_data["years"]
            years_dict_err[year_key] = {
                "error": str(e),
                "start_date": None,
                "end_date": None,
                "duration_days": None,
            }

    return future_data


def _check_year_overlaps(
    schedule_data: dict[str, Any],
    all_schedules: dict[str, Any],
    current_schedule_id: str,
    year: int,
) -> dict[str, Any]:
    """Check for overlaps with other schedules in a specific year.

    Args:
        schedule_data: The current schedule data
        all_schedules: All schedules in the config entry
        current_schedule_id: ID of the current schedule to exclude
        year: The year to check overlaps for

    Returns:
        Dictionary with overlap status and conflicting schedule details
    """
    try:
        # Get date ranges for current schedule in this year
        current_ranges = generate_schedule_dates(schedule_data, year)
        if not current_ranges:
            return {"status": "no_dates", "conflicting_schedules": []}

        current_start, current_end = current_ranges[0]
        conflicting_schedules = []

        # Check against all other schedules
        for other_id, other_schedule in all_schedules.items():
            if other_id == current_schedule_id:
                continue  # Skip self

            try:
                other_ranges = generate_schedule_dates(other_schedule, year)
                if not other_ranges:
                    continue

                other_start, other_end = other_ranges[0]

                # Check if ranges overlap
                if current_start <= other_end and current_end >= other_start:
                    conflicting_schedules.append(
                        {
                            "id": other_id,
                            "name": other_schedule.get("name", "Unknown"),
                            "start_date": other_start.isoformat(),
                            "end_date": other_end.isoformat(),
                            "overlap_start": max(
                                current_start, other_start
                            ).isoformat(),
                            "overlap_end": min(current_end, other_end).isoformat(),
                        }
                    )

            except Exception as e:  # noqa: BLE001 - diagnostics must never fail; error is recorded in output
                _LOGGER.warning(
                    "Failed to check overlap with schedule %s for year %s: %s",
                    other_id,
                    year,
                    str(e),
                )

        if conflicting_schedules:
            return {
                "status": "conflicts_found",
                "conflicting_schedules": conflicting_schedules,
                "conflict_count": len(conflicting_schedules),
            }
        else:
            return {
                "status": "no_conflicts",
                "conflicting_schedules": [],
                "conflict_count": 0,
            }

    except Exception as e:  # noqa: BLE001 - diagnostics must never fail; error is recorded in output
        _LOGGER.warning("Failed to check overlaps for year %s: %s", year, str(e))
        return {
            "status": "error",
            "error": str(e),
            "conflicting_schedules": [],
        }
