"""Switch platform for Scheduler integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Scheduler switch platform."""
    async_add_entities([SchedulerSwitch(entry)])


class SchedulerSwitch(SwitchEntity):
    """Representation of a Scheduler switch."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        self._attr_name = entry.data.get("name", "Scheduler")
        self._attr_unique_id = entry.entry_id
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._attr_is_on = False
        self.async_write_ha_state()
