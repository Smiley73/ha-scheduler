"""The Scheduler integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)

DOMAIN = "scheduler"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Scheduler from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    # Get or create device registry
    device_registry = dr.async_get(hass)
    
    schedules = entry.data.get("schedules", {})
    
    # Create hub device only if there are schedules
    if schedules:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "scheduler_hub")},
            name="Scheduler",
            manufacturer="Scheduler",
            model="Hub",
        )
        
        # Create devices for each schedule under the hub
        for schedule_id, schedule_data in schedules.items():
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, schedule_id)},
                name=schedule_data.get("name", "Schedule"),
                manufacturer="Scheduler",
                model="Schedule",
                via_device=(DOMAIN, "scheduler_hub"),
            )
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener for options flow changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a schedule device from the config entry."""
    # Don't allow removing the hub device
    if (DOMAIN, "scheduler_hub") in device_entry.identifiers:
        return False
    
    # Find and remove the schedule from the config entry data
    schedules = dict(config_entry.data.get("schedules", {}))
    
    for schedule_id in list(schedules.keys()):
        if (DOMAIN, schedule_id) in device_entry.identifiers:
            schedules.pop(schedule_id)
            
            # Update the config entry
            hass.config_entries.async_update_entry(
                config_entry,
                data={**config_entry.data, "schedules": schedules}
            )
            
            # Reload to update entities
            await hass.config_entries.async_reload(config_entry.entry_id)
            return True
    
    return False
