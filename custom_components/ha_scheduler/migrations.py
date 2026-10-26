"""Migration system for HA Scheduler integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Current version - increment when adding new migrations
CURRENT_VERSION = 2
CURRENT_MINOR_VERSION = 1


def backfill_schedule_uids(schedules: dict[str, Any]) -> dict[str, Any]:
    """Return ``schedules`` with each missing ``uid`` set to its storage key.

    Overlap validation excludes the schedule being edited by uid, and a
    missing uid made every edit conflict with itself. Schedules migrated
    from v1 are stored without one.
    """
    return {
        schedule_id: (
            schedule if "uid" in schedule else {**schedule, "uid": schedule_id}
        )
        for schedule_id, schedule in schedules.items()
    }


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to current version."""
    version = entry.version
    minor_version = entry.minor_version

    _LOGGER.debug(
        "Migrating config entry from version %s.%s to %s.%s",
        version,
        minor_version,
        CURRENT_VERSION,
        CURRENT_MINOR_VERSION,
    )

    if version == 1:
        if not await async_migrate_v1_to_v2(hass, entry):
            return False
        version = CURRENT_VERSION
        minor_version = CURRENT_MINOR_VERSION

    # Same major version with an older minor: nothing structural changes,
    # but the stored minor must be bumped or core re-offers the entry for
    # migration on every restart.
    if version == CURRENT_VERSION and minor_version < CURRENT_MINOR_VERSION:
        minor_version = CURRENT_MINOR_VERSION

    if version != entry.version or minor_version != entry.minor_version:
        hass.config_entries.async_update_entry(
            entry,
            version=version,
            minor_version=minor_version,
        )

    return True


async def async_migrate_v1_to_v2(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate from version 1 (helper) to version 2 (service).

    Changes:
    - Transform single scheduler with multiple schedules to service-based model
    - Each service gets its own calendar
    - Migrate existing schedules to the default service
    - Preserve existing entity unique IDs to avoid duplicates
    """
    _LOGGER.info("Migrating scheduler from helper to service model")

    try:
        existing_schedules = entry.options.get("schedules", {})
        existing_config = entry.options.get("configuration", {})

        # Create new service-based structure, preserving any unknown keys
        new_data = {
            **entry.data,
            "scheduler_name": entry.title,  # Use existing title as service name
        }

        new_options = {
            "services": {
                # Note: The calendar entity will use entry.entry_id as unique_id for backward compatibility
                "default": {
                    "name": entry.title,
                    "schedules": existing_schedules,
                    "configuration": existing_config,
                }
            }
        }

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
        )

        _LOGGER.info(
            "Successfully migrated scheduler '%s' with %d schedules to service model",
            entry.title,
            len(existing_schedules),
        )

        return True

    except Exception:
        _LOGGER.exception("Failed to migrate config entry")
        return False
