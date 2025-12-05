"""Binary sensor platform for Scheduler integration."""
from __future__ import annotations

import logging
from datetime import datetime

import yaml

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Scheduler binary sensor platform."""
    async_add_entities([SchedulerBinarySensor(hass, entry)])


class SchedulerBinarySensor(BinarySensorEntity):
    """Representation of a Scheduler binary sensor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        self._hass = hass
        self._entry = entry
        self._attr_name = entry.data.get("name", "Schedule")
        self._attr_unique_id = entry.entry_id
        self._attr_extra_state_attributes = {}
        self._update_extra_state_attributes()
        self._update_state()
        
        # Update every hour
        async_track_time_interval(
            hass, self._async_update_callback, timedelta(hours=1)
        )

    def _is_date_in_range(self) -> bool:
        """Check if current date is within the configured range."""
        now = datetime.now()
        current_month = now.month
        current_day = now.day
        current_weekday = now.weekday()  # Monday=0, Sunday=6
        
        schedule_type = self._entry.data.get("schedule_type", "date")
        start_month = self._entry.data.get("start_month", 1)
        end_month = self._entry.data.get("end_month", 12)
        
        # Check if current month is in range
        if start_month <= end_month:
            # Normal range (e.g., January to December)
            if not (start_month <= current_month <= end_month):
                return False
        else:
            # Wrap-around range (e.g., November to February)
            if not (current_month >= start_month or current_month <= end_month):
                return False
        
        if schedule_type == "date":
            # Date-based schedule
            start_day = self._entry.data.get("start_day", 1)
            end_day = self._entry.data.get("end_day", 31)
            
            # If we're in the start month, check if we're past the start day
            if current_month == start_month and current_day < start_day:
                return False
            
            # If we're in the end month, check if we're before the end day
            if current_month == end_month and current_day > end_day:
                return False
            
            return True
        
        else:  # week-based schedule
            start_day_of_week = self._entry.data.get("start_day_of_week", 0)
            end_day_of_week = self._entry.data.get("end_day_of_week", 6)
            start_week = self._entry.data.get("start_week", 0)
            end_week = self._entry.data.get("end_week", 4)
            
            # Calculate which week of the month we're in (0-4)
            week_of_month = (current_day - 1) // 7
            
            # Check if current week is in range
            if not (start_week <= week_of_month <= end_week):
                return False
            
            # Check if current day of week is in range
            if start_day_of_week <= end_day_of_week:
                # Normal range (e.g., Monday to Friday)
                if not (start_day_of_week <= current_weekday <= end_day_of_week):
                    return False
            else:
                # Wrap-around range (e.g., Friday to Monday)
                if not (current_weekday >= start_day_of_week or current_weekday <= end_day_of_week):
                    return False
            
            return True

    def _update_state(self) -> None:
        """Update the sensor state based on current date."""
        is_active = self._is_date_in_range()
        self._attr_is_on = is_active
        
        if is_active:
            self._attr_icon = "mdi:check-circle"
            self._attr_extra_state_attributes = {
                **self._attr_extra_state_attributes,
                "device_class": "running",
            }
        else:
            self._attr_icon = "mdi:circle-outline"

    def _update_extra_state_attributes(self) -> None:
        """Update extra state attributes."""
        schedule_type = self._entry.data.get("schedule_type", "date")
        
        attrs = {
            "schedule_type": schedule_type,
            "start_month": self._entry.data.get("start_month", 1),
            "end_month": self._entry.data.get("end_month", 12),
        }
        
        if schedule_type == "date":
            attrs["start_day"] = self._entry.data.get("start_day", 1)
            attrs["end_day"] = self._entry.data.get("end_day", 31)
        else:
            attrs["start_day_of_week"] = self._entry.data.get("start_day_of_week", 0)
            attrs["end_day_of_week"] = self._entry.data.get("end_day_of_week", 6)
            attrs["start_week"] = self._entry.data.get("start_week", 0)
            attrs["end_week"] = self._entry.data.get("end_week", 4)
        
        # Add parsed YAML config if provided
        additional_yaml = self._entry.data.get("additional_yaml", "").strip()
        if additional_yaml:
            try:
                parsed_config = yaml.safe_load(additional_yaml)
                if isinstance(parsed_config, (dict, list)):
                    attrs["config"] = parsed_config
            except yaml.YAMLError as err:
                _LOGGER.warning("Failed to parse additional_yaml: %s", err)
        
        self._attr_extra_state_attributes = attrs

    async def _async_update_callback(self, now: datetime) -> None:
        """Update callback called every hour."""
        self._update_state()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity."""
        self._attr_name = self._entry.data.get("name", "Schedule")
        self._update_state()
        self._update_extra_state_attributes()
