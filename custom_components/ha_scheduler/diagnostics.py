"""Diagnostics support for Scheduler."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DAY_NAMES
from .schedule_generator import generate_schedule_dates

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
    schedules = entry.options.get("schedules", {})
    default_config = entry.options.get("configuration", {})

    # Build schedule summary
    schedule_summary = []
    for schedule_id, schedule_data in schedules.items():
        schedule_info = {
            "id": schedule_id,
            "name": schedule_data.get("name"),
            "type": schedule_data.get("schedule_type"),
        }

        # Add type-specific fields
        if schedule_data.get("schedule_type") == "date":
            schedule_info.update(
                {
                    "start_month": schedule_data.get("start_month"),
                    "start_day": schedule_data.get("start_day"),
                    "end_month": schedule_data.get("end_month"),
                    "end_day": schedule_data.get("end_day"),
                }
            )
        elif schedule_data.get("schedule_type") == "week":
            start_day_of_week = schedule_data.get("start_day_of_week")
            end_day_of_week = schedule_data.get("end_day_of_week")
            schedule_info.update(
                {
                    "start_month": schedule_data.get("start_month"),
                    "start_week": schedule_data.get("start_week"),
                    "start_day_of_week": start_day_of_week,
                    "start_day_name": _get_day_name(start_day_of_week),
                    "end_month": schedule_data.get("end_month"),
                    "end_week": schedule_data.get("end_week"),
                    "end_day_of_week": end_day_of_week,
                    "end_day_name": _get_day_name(end_day_of_week),
                }
            )
        elif schedule_data.get("schedule_type") == "nth-day":
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

        # Include configuration if present
        if "configuration" in schedule_data:
            schedule_info["has_configuration"] = True
            schedule_info["configuration"] = schedule_data["configuration"]
        else:
            schedule_info["has_configuration"] = False

        # Add schedule dates and durations for next 3 years
        schedule_info["future_dates"] = _calculate_future_dates(schedule_data)

        schedule_summary.append(schedule_info)

    return {
        "entry": {
            "title": entry.title,
            "entry_id": entry.entry_id,
        },
        "schedules": {
            "count": len(schedules),
            "items": schedule_summary,
        },
        "default_configuration": {
            "has_default": bool(default_config),
            "configuration": default_config if default_config else None,
        },
    }


def _calculate_future_dates(schedule_data: dict[str, Any]) -> dict[str, Any]:
    """Calculate schedule dates and durations for the next 3 years.

    Returns a dictionary with yearly data and any computation warnings.
    """
    current_year = date.today().year
    future_data = {"years": {}, "warnings": []}

    for year in range(current_year, current_year + 3):
        year_key = str(year)
        try:
            date_ranges = generate_schedule_dates(schedule_data, year)

            if not date_ranges:
                future_data["warnings"].append(
                    f"No valid dates generated for year {year}"
                )
                future_data["years"][year_key] = {
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

            future_data["years"][year_key] = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "duration_days": duration,
            }

        except Exception as e:
            _LOGGER.warning(
                "Failed to calculate schedule dates for year %s: %s", year, str(e)
            )
            future_data["warnings"].append(
                f"Failed to compute dates for year {year}: {str(e)}"
            )
            future_data["years"][year_key] = {
                "error": str(e),
                "start_date": None,
                "end_date": None,
                "duration_days": None,
            }

    return future_data
