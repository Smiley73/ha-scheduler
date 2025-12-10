"""Diagnostics support for Scheduler."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


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
            schedule_info.update(
                {
                    "start_month": schedule_data.get("start_month"),
                    "start_week": schedule_data.get("start_week"),
                    "start_day_of_week": schedule_data.get("start_day_of_week"),
                    "end_month": schedule_data.get("end_month"),
                    "end_week": schedule_data.get("end_week"),
                    "end_day_of_week": schedule_data.get("end_day_of_week"),
                }
            )
        elif schedule_data.get("schedule_type") == "nth-day":
            schedule_info.update(
                {
                    "month": schedule_data.get("month"),
                    "occurrence": schedule_data.get("occurrence"),
                    "day_of_week": schedule_data.get("day_of_week"),
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
