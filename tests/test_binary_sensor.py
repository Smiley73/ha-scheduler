"""Test the Scheduler binary sensor platform."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.scheduler.const import DOMAIN


async def test_binary_sensor_setup(hass: HomeAssistant, config_entry):
    """Test binary sensor setup."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"binary_sensor.{config_entry.data['name'].lower().replace(' ', '_')}"
    
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["start_month"] == 1
    assert state.attributes["end_month"] == 12
    assert state.attributes["schedule_type"] == "date"


async def test_binary_sensor_date_in_range(hass: HomeAssistant, config_entry):
    """Test binary sensor when date is in range."""
    # Mock current date to be within range (June 15)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = f"binary_sensor.{config_entry.data['name'].lower().replace(' ', '_')}"
        
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"
        assert state.attributes["icon"] == "mdi:check-circle"


async def test_binary_sensor_date_out_of_range(hass: HomeAssistant):
    """Test binary sensor when date is out of range."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    # Create config entry active only in June
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Schedule",
        data={
            "name": "Test Schedule",
            "start_month": 6,
            "end_month": 6,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 30,
        },
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
    
    # Mock current date to be outside range (July 1)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 7, 1)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = f"binary_sensor.{config_entry.data['name'].lower().replace(' ', '_')}"
        
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "off"
        assert state.attributes["icon"] == "mdi:circle-outline"


async def test_binary_sensor_week_based(hass: HomeAssistant):
    """Test binary sensor with week-based schedule."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    # Create config entry with week-based schedule (first week, Monday-Friday)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Schedule",
        data={
            "name": "Test Schedule",
            "schedule_type": "week",
            "start_month": 1,
            "end_month": 12,
            "start_day_of_week": 0,  # Monday
            "end_day_of_week": 4,    # Friday
            "start_week": 0,
            "end_week": 0,
        },
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
    
    # Mock current date to be first Monday of June (June 2, 2025)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 2)  # Monday, first week
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = f"binary_sensor.{config_entry.data['name'].lower().replace(' ', '_')}"
        
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"
        assert state.attributes["schedule_type"] == "week"
