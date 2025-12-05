"""Binary sensor platform for Scheduler integration."""
from __future__ import annotations

import logging
from datetime import datetime

import yaml

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval, async_track_state_change_event
from datetime import timedelta

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Scheduler binary sensor platform."""
    schedules = entry.data.get("schedules", {})
    
    entities = []
    
    # Create individual schedule sensors
    schedule_sensors = []
    for schedule_id, schedule_data in schedules.items():
        sensor = SchedulerBinarySensor(hass, entry, schedule_id, schedule_data)
        entities.append(sensor)
        schedule_sensors.append(sensor)
    
    # Create aggregated hub sensor if there are schedules
    if schedule_sensors:
        hub_sensor = SchedulerHubBinarySensor(hass, entry, schedule_sensors)
        entities.append(hub_sensor)
    
    async_add_entities(entities)


class SchedulerBinarySensor(BinarySensorEntity):
    """Representation of a Scheduler binary sensor."""

    def __init__(
        self, 
        hass: HomeAssistant, 
        entry: ConfigEntry, 
        schedule_id: str, 
        schedule_data: dict
    ) -> None:
        """Initialize the binary sensor."""
        self._hass = hass
        self._entry = entry
        self._schedule_id = schedule_id
        self._schedule_data = schedule_data
        schedule_name = schedule_data.get("name", "Schedule")
        self._attr_name = schedule_name
        self._attr_unique_id = f"{entry.entry_id}_{schedule_id}"
        # Create entity_id from schedule name
        # Remove " Schedule" suffix if present, then convert to snake_case
        entity_name = schedule_name.lower()
        if entity_name.endswith(" schedule"):
            entity_name = entity_name[:-9]  # Remove " schedule"
        entity_name = entity_name.replace(" ", "_")
        self.entity_id = f"binary_sensor.scheduler_{entity_name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, schedule_id)},
            "name": schedule_name,
            "manufacturer": "Scheduler",
            "model": "Schedule",
            "via_device": (DOMAIN, "scheduler_hub"),
        }
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
        
        schedule_type = self._schedule_data.get("schedule_type", "date")
        start_month = self._schedule_data.get("start_month", 1)
        end_month = self._schedule_data.get("end_month", 12)
        
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
            start_day = self._schedule_data.get("start_day", 1)
            end_day = self._schedule_data.get("end_day", 31)
            
            # If we're in the start month, check if we're past the start day
            if current_month == start_month and current_day < start_day:
                return False
            
            # If we're in the end month, check if we're before the end day
            if current_month == end_month and current_day > end_day:
                return False
            
            return True
        
        else:  # week-based schedule
            start_day_of_week = self._schedule_data.get("start_day_of_week", 0)
            end_day_of_week = self._schedule_data.get("end_day_of_week", 6)
            start_week = self._schedule_data.get("start_week", 0)
            end_week = self._schedule_data.get("end_week", 4)
            
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
        schedule_type = self._schedule_data.get("schedule_type", "date")
        
        attrs = {
            "schedule_type": schedule_type,
            "schedule_id": self._schedule_id,
            "start_month": self._schedule_data.get("start_month", 1),
            "end_month": self._schedule_data.get("end_month", 12),
        }
        
        if schedule_type == "date":
            attrs["start_day"] = self._schedule_data.get("start_day", 1)
            attrs["end_day"] = self._schedule_data.get("end_day", 31)
        else:
            attrs["start_day_of_week"] = self._schedule_data.get("start_day_of_week", 0)
            attrs["end_day_of_week"] = self._schedule_data.get("end_day_of_week", 6)
            attrs["start_week"] = self._schedule_data.get("start_week", 0)
            attrs["end_week"] = self._schedule_data.get("end_week", 4)
        
        # Add parsed YAML config if provided
        additional_yaml = self._schedule_data.get("additional_yaml", "").strip()
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
        # Refresh schedule data from entry
        schedules = self._entry.data.get("schedules", {})
        if self._schedule_id in schedules:
            self._schedule_data = schedules[self._schedule_id]
            schedule_name = self._schedule_data.get("name", "Schedule")
            self._attr_name = schedule_name
        
        self._update_state()
        self._update_extra_state_attributes()



class SchedulerHubBinarySensor(BinarySensorEntity):
    """Aggregated binary sensor that represents all schedule sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        schedule_sensors: list[SchedulerBinarySensor],
    ) -> None:
        """Initialize the hub binary sensor."""
        self._hass = hass
        self._entry = entry
        self._schedule_sensors = schedule_sensors
        self._attr_name = "Scheduler"
        self._attr_unique_id = f"{entry.entry_id}_hub"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "scheduler_hub")},
            "name": "Scheduler",
            "manufacturer": "Scheduler",
            "model": "Hub",
        }
        self._attr_extra_state_attributes = {}
        self._unsub_state_listener = None
        self._update_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Track state changes of all schedule sensors
        entity_ids = [sensor.entity_id for sensor in self._schedule_sensors]
        
        @callback
        def state_change_listener(event):
            """Handle state changes of schedule sensors."""
            self._update_state()
            self.async_write_ha_state()
        
        self._unsub_state_listener = async_track_state_change_event(
            self._hass, entity_ids, state_change_listener
        )
        
        # Update every hour as well
        async_track_time_interval(
            self._hass, self._async_update_callback, timedelta(hours=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._unsub_state_listener:
            self._unsub_state_listener()
        await super().async_will_remove_from_hass()

    def _update_state(self) -> None:
        """Update the sensor state based on schedule sensors."""
        active_schedules = []
        
        # Find all active schedules
        for sensor in self._schedule_sensors:
            if sensor.is_on:
                active_schedules.append(sensor)
        
        # Set state to true if any schedule is active
        self._attr_is_on = len(active_schedules) > 0
        
        # Update attributes
        attrs = {}
        
        if active_schedules:
            # Use the first active schedule for the attributes
            active_sensor = active_schedules[0]
            attrs["active_schedule"] = active_sensor.name
            
            # Duplicate the additional_yaml attribute if it exists
            sensor_attrs = active_sensor.extra_state_attributes or {}
            if "config" in sensor_attrs:
                attrs["config"] = sensor_attrs["config"]
            
            self._attr_icon = "mdi:check-circle"
        else:
            attrs["active_schedule"] = "None"
            self._attr_icon = "mdi:circle-outline"
        
        self._attr_extra_state_attributes = attrs

    async def _async_update_callback(self, now: datetime) -> None:
        """Update callback called every hour."""
        self._update_state()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity."""
        self._update_state()
