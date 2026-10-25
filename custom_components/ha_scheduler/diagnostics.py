"""Diagnostics support for Scheduler."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DAY_NAMES_DISPLAY,
    SCHEDULE_TYPE_DATE,
    SCHEDULE_TYPE_HOLIDAY,
    SCHEDULE_TYPE_NTH_DAY,
    SCHEDULE_TYPE_WEEK,
)
from .holiday_importer import async_prime_holiday_cache, get_holidays_library_version
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

# Years of future dates (starting with the current year) reported per schedule.
_FUTURE_YEARS = 3


def _get_day_name(day_of_week: int | None) -> str | None:
    """Return the display name for a day number (0=Monday), or None if invalid."""
    if day_of_week is None or not (0 <= day_of_week <= 6):
        return None
    return DAY_NAMES_DISPLAY[day_of_week]


def _week_type_display(week_type: str) -> str:
    return (
        "First full week (entirely within month)"
        if week_type == "full"
        else "First week (may start in previous month)"
    )


def _error_year(error: str) -> dict[str, Any]:
    return {
        "error": error,
        "start_date": None,
        "end_date": None,
        "duration_days": None,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    services = entry.options.get("services", {})

    current_year = dt_util.now().date().year
    all_schedules = [
        schedule
        for service_data in services.values()
        for schedule in service_data.get("schedules", {}).values()
    ]
    await async_prime_holiday_cache(
        all_schedules, range(current_year, current_year + _FUTURE_YEARS)
    )

    services_diagnostics = {}
    total_schedules = 0

    for service_id, service_data in services.items():
        schedules = service_data.get("schedules", {})
        service_config = service_data.get("configuration", {})
        total_schedules += len(schedules)

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
        "environment": {
            "holidays_version": await hass.async_add_executor_job(
                get_holidays_library_version
            ),
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
    schedule_type = schedule_data.get("schedule_type")
    schedule_info = {
        "id": schedule_id,
        "name": schedule_data.get("name"),
        "type": schedule_type,
    }

    if schedule_type == SCHEDULE_TYPE_DATE:
        schedule_info.update(
            {
                "start_month": schedule_data.get("start_month"),
                "start_day": schedule_data.get("start_day"),
                "end_month": schedule_data.get("end_month"),
                "end_day": schedule_data.get("end_day"),
            }
        )
    elif schedule_type == SCHEDULE_TYPE_WEEK:
        start_day_of_week = schedule_data.get("start_day_of_week")
        end_day_of_week = schedule_data.get("end_day_of_week")
        start_week_type = schedule_data.get("start_week_type", "partial")
        end_week_type = schedule_data.get("end_week_type", "partial")

        schedule_info.update(
            {
                "start_month": schedule_data.get("start_month"),
                "start_week": schedule_data.get("start_week"),
                "start_week_type": start_week_type,
                "start_week_type_display": _week_type_display(start_week_type),
                "start_day_of_week": start_day_of_week,
                "start_day_name": _get_day_name(start_day_of_week)
                if start_day_of_week is not None
                else "Whole week",
                "end_month": schedule_data.get("end_month"),
                "end_week": schedule_data.get("end_week"),
                "end_week_type": end_week_type,
                "end_week_type_display": _week_type_display(end_week_type),
                "end_day_of_week": end_day_of_week,
                "end_day_name": _get_day_name(end_day_of_week)
                if end_day_of_week is not None
                else "Whole week",
                "country_code": schedule_data.get("country_code"),
            }
        )
    elif schedule_type == SCHEDULE_TYPE_NTH_DAY:
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
    elif schedule_type == SCHEDULE_TYPE_HOLIDAY:
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

    if "configuration" in schedule_data:
        schedule_info["has_configuration"] = True
        schedule_info["configuration"] = async_redact_data(
            schedule_data["configuration"], _REDACT_KEYS
        )
    else:
        schedule_info["has_configuration"] = False

    schedule_info["future_dates"] = _calculate_future_dates(
        schedule_data, all_schedules, schedule_id
    )

    return schedule_info


def _calculate_future_dates(
    schedule_data: dict[str, Any],
    all_schedules: dict[str, Any],
    current_schedule_id: str,
) -> dict[str, Any]:
    """Calculate dates, durations and overlaps for the next few years."""
    current_year = dt_util.now().date().year
    years: dict[str, Any] = {}
    warnings: list[str] = []

    for year in range(current_year, current_year + _FUTURE_YEARS):
        year_key = str(year)
        try:
            date_ranges = generate_schedule_dates(schedule_data, year)

            if not date_ranges:
                warnings.append(f"No valid dates generated for year {year}")
                years[year_key] = _error_year("No valid dates generated")
                continue

            # Take the first date range (most schedules have only one per year)
            start_date, end_date = date_ranges[0]

            years[year_key] = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                # +1 to include both start and end days
                "duration_days": (end_date - start_date).days + 1,
                "overlaps": _check_year_overlaps(
                    schedule_data, all_schedules, current_schedule_id, year
                ),
            }

        except Exception as e:  # noqa: BLE001 - diagnostics must never fail; error is recorded in output
            _LOGGER.warning(
                "Failed to calculate schedule dates for year %s: %s", year, str(e)
            )
            warnings.append(f"Failed to compute dates for year {year}: {e!s}")
            years[year_key] = _error_year(str(e))

    return {"years": years, "warnings": warnings}


def _check_year_overlaps(
    schedule_data: dict[str, Any],
    all_schedules: dict[str, Any],
    current_schedule_id: str,
    year: int,
) -> dict[str, Any]:
    """Check for overlaps with other schedules in a specific year."""
    try:
        current_ranges = generate_schedule_dates(schedule_data, year)
        if not current_ranges:
            return {"status": "no_dates", "conflicting_schedules": []}

        current_start, current_end = current_ranges[0]
        conflicting_schedules = []

        for other_id, other_schedule in all_schedules.items():
            if other_id == current_schedule_id:
                continue

            try:
                other_ranges = generate_schedule_dates(other_schedule, year)
                if not other_ranges:
                    continue

                other_start, other_end = other_ranges[0]

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

        return {
            "status": "conflicts_found" if conflicting_schedules else "no_conflicts",
            "conflicting_schedules": conflicting_schedules,
            "conflict_count": len(conflicting_schedules),
        }

    except Exception as e:  # noqa: BLE001 - diagnostics must never fail; error is recorded in output
        _LOGGER.warning("Failed to check overlaps for year %s: %s", year, str(e))
        return {
            "status": "error",
            "error": str(e),
            "conflicting_schedules": [],
        }
