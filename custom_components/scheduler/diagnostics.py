"""Diagnostics support for Scheduler integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    schedules = entry.data.get("schedules", {})
    entity_reg = er.async_get(hass)

    # Collect entity states by looking up entities from the registry
    entity_states = {}
    for schedule_id, schedule_data in schedules.items():
        # Find entity by unique_id
        unique_id = f"{entry.entry_id}_{schedule_id}"
        entity_entry = entity_reg.async_get_entity_id(
            "binary_sensor", DOMAIN, unique_id
        )

        if entity_entry:
            state = hass.states.get(entity_entry)
            if state:
                entity_states[schedule_id] = {
                    "entity_id": entity_entry,
                    "state": state.state,
                    "attributes": dict(state.attributes),
                }

    # Also get the hub sensor state
    hub_unique_id = f"{entry.entry_id}_hub"
    hub_entity_id = entity_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, hub_unique_id
    )
    hub_info = None
    if hub_entity_id:
        hub_state = hass.states.get(hub_entity_id)
        if hub_state:
            hub_info = {
                "entity_id": hub_entity_id,
                "state": hub_state.state,
                "attributes": dict(hub_state.attributes),
            }

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
        },
        "schedules": schedules,
        "schedule_count": len(schedules),
        "entity_states": entity_states,
        "hub_sensor": hub_info,
    }
