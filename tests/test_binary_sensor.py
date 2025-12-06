"""Test the Scheduler binary sensor platform."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.scheduler.const import DOMAIN


async def test_binary_sensor_setup(hass: HomeAssistant, hub_entry):
    """Test binary sensor setup."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "binary_sensor.scheduler_test_schedule"
    
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["start_month"] == 1
    assert state.attributes["end_month"] == 12
    assert state.attributes["schedule_type"] == "date"
    assert state.attributes["schedule_id"] == "test_schedule_1"


async def test_binary_sensor_date_in_range(hass: HomeAssistant, hub_entry):
    """Test binary sensor when date is in range."""
    # Mock current date to be within range (June 10)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 10)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_test_schedule"
        
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"


async def test_binary_sensor_date_out_of_range(hass: HomeAssistant):
    """Test binary sensor when date is out of range."""
    # Create hub entry with schedule active only in June
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "june_schedule": {
                    "name": "June Schedule",
                    "start_month": 6,
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 30,
                },
            },
        },
        entry_id="test_june_hub",
    )
    
    # Mock current date to be outside range (July 1)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 7, 1)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_june_schedule"
        
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "off"


async def test_binary_sensor_week_based(hass: HomeAssistant):
    """Test binary sensor with week-based schedule."""
    # Create hub entry with week-based schedule (first week, Monday-Friday)
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "week_schedule": {
                    "name": "Week Schedule",
                    "schedule_type": "week",
                    "start_month": 1,
                    "end_month": 12,
                    "start_day_of_week": 0,  # Monday
                    "end_day_of_week": 4,    # Friday
                    "start_week": 0,
                    "end_week": 0,
                },
            },
        },
        entry_id="test_week_hub",
    )
    
    # Mock current date to be first Monday of June (June 2, 2025)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 2)  # Monday, first week
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_week_schedule"
        
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"
        assert state.attributes["schedule_type"] == "week"


async def test_binary_sensor_with_additional_yaml(hass: HomeAssistant):
    """Test binary sensor with additional YAML config."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "config_schedule": {
                    "name": "Config Schedule",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                    "additional_yaml": "enabled: true\ntimeout: 30",
                },
            },
        },
        entry_id="test_config_hub",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_config_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert "config" in state.attributes
        assert state.attributes["config"]["enabled"] is True
        assert state.attributes["config"]["timeout"] == 30


async def test_multiple_schedules(hass: HomeAssistant):
    """Test multiple schedules in one hub."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "schedule_1": {
                    "name": "Schedule 1",
                    "start_month": 1,
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
                "schedule_2": {
                    "name": "Schedule 2",
                    "start_month": 7,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
            },
        },
        entry_id="test_multi_hub",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        # Check both entities exist
        state1 = hass.states.get("binary_sensor.scheduler_schedule_1")
        state2 = hass.states.get("binary_sensor.scheduler_schedule_2")
        
        assert state1
        assert state2
        
        # Schedule 1 should be on (June is in range)
        assert state1.state == "on"
        
        # Schedule 2 should be off (June is not in range)
        assert state2.state == "off"


async def test_binary_sensor_month_wrap_around(hass: HomeAssistant):
    """Test binary sensor with month wrap-around (Nov-Feb)."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "winter_schedule": {
                    "name": "Winter Schedule",
                    "start_month": 11,  # November
                    "end_month": 2,     # February
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 28,
                },
            },
        },
        entry_id="test_winter_hub",
    )
    
    # Test date in December (should be active)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 12, 15)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_winter_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"


async def test_binary_sensor_week_wrap_around_days(hass: HomeAssistant):
    """Test binary sensor with day of week wrap-around (Fri-Mon)."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "weekend_schedule": {
                    "name": "Weekend Schedule",
                    "schedule_type": "week",
                    "start_month": 1,
                    "end_month": 12,
                    "start_day_of_week": 4,  # Friday
                    "end_day_of_week": 0,    # Monday (wrap around)
                    "start_week": 0,
                    "end_week": 4,
                },
            },
        },
        entry_id="test_weekend_hub",
    )
    
    # Test on Saturday (should be active)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 7)  # Saturday
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_weekend_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"



async def test_hub_sensor_created(hass: HomeAssistant, hub_entry):
    """Test that hub sensor is created."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Check hub sensor exists
    hub_state = hass.states.get("binary_sensor.scheduler")
    assert hub_state
    assert hub_state.name == "Scheduler"


async def test_hub_sensor_aggregates_active_schedules(hass: HomeAssistant):
    """Test that hub sensor is on when any schedule is active."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "summer_schedule": {
                    "name": "Summer Schedule",
                    "start_month": 6,
                    "end_month": 8,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
                "winter_schedule": {
                    "name": "Winter Schedule",
                    "start_month": 12,
                    "end_month": 2,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 28,
                },
            },
        },
        entry_id="test_hub_aggregate",
    )
    
    # Test in summer (June) - summer schedule should be active
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        hub_state = hass.states.get("binary_sensor.scheduler")
        assert hub_state
        assert hub_state.state == "on"
        assert hub_state.attributes["active_schedule"] == "Summer Schedule"


async def test_hub_sensor_off_when_no_schedules_active(hass: HomeAssistant):
    """Test that hub sensor is off when no schedules are active."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "summer_schedule": {
                    "name": "Summer Schedule",
                    "start_month": 6,
                    "end_month": 8,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
                "winter_schedule": {
                    "name": "Winter Schedule",
                    "start_month": 12,
                    "end_month": 2,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 28,
                },
            },
        },
        entry_id="test_hub_off",
    )
    
    # Test in April - no schedules should be active
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 4, 15)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        hub_state = hass.states.get("binary_sensor.scheduler")
        assert hub_state
        assert hub_state.state == "off"
        assert hub_state.attributes["active_schedule"] == "None"


async def test_hub_sensor_duplicates_yaml_config(hass: HomeAssistant):
    """Test that hub sensor duplicates additional_yaml from active schedule."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "config_schedule": {
                    "name": "Config Schedule",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                    "additional_yaml": "mode: heat\ntemperature: 20",
                },
            },
        },
        entry_id="test_hub_yaml",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        hub_state = hass.states.get("binary_sensor.scheduler")
        assert hub_state
        assert hub_state.state == "on"
        assert hub_state.attributes["active_schedule"] == "Config Schedule"
        assert "config" in hub_state.attributes
        assert hub_state.attributes["config"]["mode"] == "heat"
        assert hub_state.attributes["config"]["temperature"] == 20


async def test_hub_sensor_multiple_active_schedules(hass: HomeAssistant):
    """Test that hub sensor shows first active schedule when multiple are active."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "schedule_a": {
                    "name": "Schedule A",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                    "additional_yaml": "priority: high",
                },
                "schedule_b": {
                    "name": "Schedule B",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                    "additional_yaml": "priority: low",
                },
            },
        },
        entry_id="test_hub_multiple",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        hub_state = hass.states.get("binary_sensor.scheduler")
        assert hub_state
        assert hub_state.state == "on"
        # Should show one of the active schedules
        assert hub_state.attributes["active_schedule"] in ["Schedule A", "Schedule B"]
        # Should have config from the active schedule
        assert "config" in hub_state.attributes



async def test_hub_sensor_attribute_name_change(hass: HomeAssistant, hub_entry):
    """Test that hub sensor uses 'active_schedule' attribute name."""
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        hub_state = hass.states.get("binary_sensor.scheduler")
        assert hub_state
        # Verify the attribute is named "active_schedule"
        assert "active_schedule" in hub_state.attributes
        # Verify old attribute name doesn't exist
        assert "schedule" not in hub_state.attributes
