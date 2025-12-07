"""The Scheduler integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.CALENDAR]

type SchedulerConfigEntry = ConfigEntry[list[dict]]


async def async_setup_entry(hass: HomeAssistant, entry: SchedulerConfigEntry) -> bool:
    """Set up Scheduler from a config entry."""
    # Initialize runtime data with empty schedule list
    entry.runtime_data = []

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SchedulerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
