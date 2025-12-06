"""Binary sensor platform for Scheduler integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import yaml
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# No parallel update limits needed - all operations are local and read-only
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Scheduler binary sensor platform."""
    from homeassistant.helpers import entity_registry as er

    schedules = entry.data.get("schedules", {})
    entity_reg = er.async_get(hass)

    entities = []

    # Create individual schedule sensors
    schedule_sensors = []
    for schedule_id, schedule_data in schedules.items():
        sensor = SchedulerBinarySensor(hass, entry, schedule_id, schedule_data)

        # Pre-register entity with custom entity_id to ensure prefix
        schedule_name = schedule_data.get("name", "Schedule")
        suggested_entity_id = f"scheduler_{schedule_name.lower().replace(' ', '_')}"
        unique_id = f"{entry.entry_id}_{schedule_id}"

        # Check if entity exists, if not create it with our suggested ID
        existing_entity_id = entity_reg.async_get_entity_id(
            "binary_sensor", DOMAIN, unique_id
        )
        if not existing_entity_id:
            entity_reg.async_get_or_create(
                "binary_sensor",
                DOMAIN,
                unique_id,
                suggested_object_id=suggested_entity_id,
            )

        entities.append(sensor)
        schedule_sensors.append(sensor)

    # Create aggregated hub sensor if there are schedules
    if schedule_sensors:
        hub_sensor = SchedulerHubBinarySensor(hass, entry, schedule_sensors)
        entities.append(hub_sensor)

    async_add_entities(entities)


class SchedulerBinarySensor(BinarySensorEntity):
    """Representation of a Scheduler binary sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule"
    _attr_name = None  # Use device name only

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        schedule_id: str,
        schedule_data: dict,
    ) -> None:
        """Initialize the binary sensor."""
        self._hass = hass
        self._entry = entry
        self._schedule_id = schedule_id
        self._schedule_data = schedule_data
        schedule_name = schedule_data.get("name", "Schedule")
        # Store schedule name for hub sensor to access
        self._schedule_name = schedule_name
        self._attr_unique_id = f"{entry.entry_id}_{schedule_id}"
        self._attr_should_poll = False
        self._attr_available = True
        self._unavailable_logged = False
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
        async_track_time_interval(hass, self._async_update_callback, timedelta(hours=1))

    def _is_date_in_range(self) -> bool:
        """Check if current date is within the configured range."""
        # Validate schedule data exists and has required fields
        if not self._schedule_data:
            if not self._unavailable_logged:
                _LOGGER.warning(
                    "Schedule %s has no data, marking unavailable", self._schedule_id
                )
                self._unavailable_logged = True
            self._attr_available = False
            return False

        # Mark as available if we have valid data
        if not self._attr_available and self._unavailable_logged:
            _LOGGER.info("Schedule %s is back online", self._schedule_id)
            self._unavailable_logged = False
        self._attr_available = True

        now = datetime.now()
        current_month = now.month
        current_day = now.day
        now.weekday()  # Monday=0, Sunday=6

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

            # Calculate the actual start and end dates for this month/year
            # Find the first occurrence of start_day_of_week in start_week
            # and last occurrence of end_day_of_week in end_week
            
            # Calculate start date: first start_day_of_week in start_week
            start_week_first_day = start_week * 7 + 1
            start_date_candidate = start_week_first_day
            
            # Find the first occurrence of start_day_of_week in the start week
            for day in range(start_week_first_day, min(start_week_first_day + 7, 32)):
                try:
                    check_date = datetime(now.year, current_month, day)
                    if check_date.weekday() == start_day_of_week:
                        start_date_candidate = day
                        break
                except ValueError:
                    break
            
            # Calculate end date: last occurrence of end_day_of_week in end_week
            end_week_first_day = end_week * 7 + 1
            end_date_candidate = end_week_first_day
            
            # Find the last occurrence of end_day_of_week in the end week
            for day in range(end_week_first_day, min(end_week_first_day + 7, 32)):
                try:
                    check_date = datetime(now.year, current_month, day)
                    if check_date.weekday() == end_day_of_week:
                        end_date_candidate = day
                except ValueError:
                    break
            
            # Check if current day is within the calculated range
            if not (start_date_candidate <= current_day <= end_date_candidate):
                return False

            return True

    def _update_state(self) -> None:
        """Update the sensor state based on current date."""
        is_active = self._is_date_in_range()
        self._attr_is_on = is_active

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
            # Store schedule name for hub sensor to access
            self._schedule_name = schedule_name
        else:
            # Schedule was removed from config
            if not self._unavailable_logged:
                _LOGGER.warning(
                    "Schedule %s no longer exists in config, marking unavailable",
                    self._schedule_id,
                )
                self._unavailable_logged = True
            self._attr_available = False
            self._schedule_data = {}
            return

        self._update_state()
        self._update_extra_state_attributes()


class SchedulerHubBinarySensor(BinarySensorEntity):
    """Aggregated binary sensor that represents all schedule sensors."""

    _attr_has_entity_name = True
    _attr_translation_key = "hub"
    _attr_name = None  # Use device name only

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
        self._attr_unique_id = f"{entry.entry_id}_hub"
        self._attr_should_poll = False
        self._attr_available = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "scheduler_hub")},
            "name": "Scheduler",
            "manufacturer": "Scheduler",
            "model": "Hub",
        }
        self._attr_extra_state_attributes = {}
        self._attr_is_on = False
        self._unsub_state_listener = None
        # Don't call _update_state() here - entity_ids aren't set yet

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        # Now that entities are added, do initial state update
        self._update_state()

        # Track state changes of all schedule sensors
        entity_ids = [
            sensor.entity_id for sensor in self._schedule_sensors if sensor.entity_id
        ]

        @callback
        def state_change_listener(event):
            """Handle state changes of schedule sensors."""
            self._update_state()
            self.async_write_ha_state()

        if entity_ids:
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
        available_count = 0

        # Find all active schedules by checking actual state from state machine
        for sensor in self._schedule_sensors:
            # Check if entity exists and is enabled in the state machine
            if sensor.entity_id:
                state = self._hass.states.get(sensor.entity_id)
                # Count available sensors
                if state and state.state != "unavailable":
                    available_count += 1
                # Only consider if state exists and is "on"
                if state and state.state == "on":
                    active_schedules.append(sensor)

        # Hub is available if at least one schedule sensor is available
        self._attr_available = available_count > 0

        # Set state to true if any schedule is active
        self._attr_is_on = len(active_schedules) > 0

        # Update attributes
        attrs = {}

        if active_schedules:
            # Use the first active schedule for the attributes
            active_sensor = active_schedules[0]
            # Get schedule name from the sensor's stored name
            schedule_name = getattr(active_sensor, "_schedule_name", "Unknown")
            attrs["active_schedule"] = schedule_name

            # Duplicate the additional_yaml attribute if it exists
            sensor_attrs = active_sensor.extra_state_attributes or {}
            if "config" in sensor_attrs:
                attrs["config"] = sensor_attrs["config"]
        else:
            attrs["active_schedule"] = "None"

        self._attr_extra_state_attributes = attrs

    async def _async_update_callback(self, now: datetime) -> None:
        """Update callback called every hour."""
        self._update_state()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity."""
        self._update_state()
