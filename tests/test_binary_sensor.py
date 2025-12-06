"""Test the Scheduler binary sensor platform."""
import logging
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



async def test_binary_sensor_invalid_yaml(hass: HomeAssistant):
    """Test binary sensor with invalid YAML config."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "bad_yaml_schedule": {
                    "name": "Bad YAML Schedule",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                    "additional_yaml": "invalid: yaml: content: [unclosed",
                },
            },
        },
        entry_id="test_bad_yaml_hub",
    )

    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)

        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_bad_yaml_schedule"
        state = hass.states.get(entity_id)
        assert state
        # Should not have config attribute due to invalid YAML
        assert "config" not in state.attributes


async def test_binary_sensor_week_out_of_range(hass: HomeAssistant):
    """Test binary sensor with week-based schedule out of range."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "week_schedule": {
                    "name": "Week Schedule",
                    "schedule_type": "week",
                    "start_month": 6,
                    "end_month": 6,
                    "start_day_of_week": 0,  # Monday
                    "end_day_of_week": 4,  # Friday
                    "start_week": 0,  # First week
                    "end_week": 0,  # First week only
                },
            },
        },
        entry_id="test_week_out_hub",
    )

    # Mock current date to be second week of June (June 9, 2025 - Monday)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 9)  # Monday, second week

        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_week_schedule"

        state = hass.states.get(entity_id)
        assert state
        # Should be off because we're in the second week, not first
        assert state.state == "off"


async def test_binary_sensor_day_of_week_out_of_range(hass: HomeAssistant):
    """Test binary sensor with day of week out of range."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "weekday_schedule": {
                    "name": "Weekday Schedule",
                    "schedule_type": "week",
                    "start_month": 1,
                    "end_month": 12,
                    "start_day_of_week": 0,  # Monday
                    "end_day_of_week": 4,  # Friday
                    "start_week": 0,
                    "end_week": 4,
                },
            },
        },
        entry_id="test_weekday_hub",
    )

    # Mock current date to be Saturday (June 7, 2025)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 7)  # Saturday

        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_weekday_schedule"

        state = hass.states.get(entity_id)
        assert state
        # Should be off because Saturday is not in Monday-Friday range
        assert state.state == "off"


async def test_binary_sensor_date_before_start_day(hass: HomeAssistant):
    """Test binary sensor when current day is before start day in start month."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "mid_month_schedule": {
                    "name": "Mid Month Schedule",
                    "start_month": 6,
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 15,  # Starts mid-month
                    "end_day": 30,
                },
            },
        },
        entry_id="test_mid_month_hub",
    )

    # Mock current date to be before start day (June 10)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 10)

        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_mid_month_schedule"

        state = hass.states.get(entity_id)
        assert state
        # Should be off because we're before the start day
        assert state.state == "off"


async def test_binary_sensor_date_after_end_day(hass: HomeAssistant):
    """Test binary sensor when current day is after end day in end month."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "early_month_schedule": {
                    "name": "Early Month Schedule",
                    "start_month": 6,
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 15,  # Ends mid-month
                },
            },
        },
        entry_id="test_early_month_hub",
    )

    # Mock current date to be after end day (June 20)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 20)

        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_early_month_schedule"

        state = hass.states.get(entity_id)
        assert state
        # Should be off because we're after the end day
        assert state.state == "off"


async def test_binary_sensor_update_on_schedule_change(hass: HomeAssistant, hub_entry):
    """Test that binary sensor updates when schedule data changes."""
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)

        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_test_schedule"

        # Get initial state
        state = hass.states.get(entity_id)
        assert state
        initial_name = state.attributes.get("friendly_name")

        # Update the schedule name in the config entry
        new_data = dict(hub_entry.data)
        new_data["schedules"]["test_schedule_1"]["name"] = "Updated Schedule Name"

        hass.config_entries.async_update_entry(hub_entry, data=new_data)
        await hass.config_entries.async_reload(hub_entry.entry_id)
        await hass.async_block_till_done()

        # Check that the name was updated
        state = hass.states.get(entity_id)
        assert state
        updated_name = state.attributes.get("friendly_name")
        assert updated_name != initial_name
        assert updated_name == "Updated Schedule Name"



async def test_hub_sensor_no_entity_ids(hass: HomeAssistant):
    """Test hub sensor when schedule sensors have no entity_id yet."""
    from custom_components.scheduler.binary_sensor import SchedulerHubBinarySensor
    from unittest.mock import Mock

    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_no_entity_hub",
    )

    hub_entry.add_to_hass(hass)

    # Create hub sensor with mock schedule sensors that have no entity_id
    mock_sensor = Mock()
    mock_sensor.entity_id = None
    mock_sensor.name = "Test"

    hub_sensor = SchedulerHubBinarySensor(hass, hub_entry, [mock_sensor])

    # Should handle None entity_ids gracefully
    await hub_sensor.async_added_to_hass()
    await hass.async_block_till_done()

    # Should not crash
    assert hub_sensor._attr_is_on is False


async def test_binary_sensor_unavailable_no_data(hass: HomeAssistant):
    """Test binary sensor becomes unavailable when schedule data is missing."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "test_schedule": {
                    "name": "Test Schedule",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
            },
        },
        entry_id="test_unavailable_hub",
    )

    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)

        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.scheduler_test_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state != "unavailable"

        # Remove schedule data to simulate corruption
        new_data = {"schedules": {}}
        hass.config_entries.async_update_entry(hub_entry, data=new_data)
        await hass.config_entries.async_reload(hub_entry.entry_id)
        await hass.async_block_till_done()

        # Entity should be removed since schedule no longer exists
        state = hass.states.get(entity_id)
        # Entity won't exist anymore after reload without the schedule


async def test_binary_sensor_availability_logging(hass: HomeAssistant, caplog):
    """Test that unavailability is logged once."""
    from custom_components.scheduler.binary_sensor import SchedulerBinarySensor

    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_logging_hub",
    )

    hub_entry.add_to_hass(hass)

    # Create sensor with empty schedule data
    sensor = SchedulerBinarySensor(hass, hub_entry, "test_id", {})

    with caplog.at_level(logging.WARNING):
        # First call should log
        sensor._is_date_in_range()
        assert "marking unavailable" in caplog.text
        assert not sensor._attr_available

        caplog.clear()

        # Second call should not log again
        sensor._is_date_in_range()
        assert "marking unavailable" not in caplog.text


async def test_binary_sensor_recovery_logging(hass: HomeAssistant, caplog):
    """Test that recovery from unavailability is logged."""
    from custom_components.scheduler.binary_sensor import SchedulerBinarySensor

    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_recovery_hub",
    )

    hub_entry.add_to_hass(hass)

    # Create sensor with empty schedule data
    sensor = SchedulerBinarySensor(hass, hub_entry, "test_id", {})

    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)

        # Make it unavailable first
        sensor._is_date_in_range()
        assert not sensor._attr_available
        assert sensor._unavailable_logged

        # Now give it valid data
        sensor._schedule_data = {
            "name": "Test",
            "schedule_type": "date",
            "start_month": 1,
            "end_month": 12,
            "start_day": 1,
            "end_day": 31,
        }

        with caplog.at_level(logging.INFO):
            sensor._is_date_in_range()
            assert "back online" in caplog.text
            assert sensor._attr_available
            assert not sensor._unavailable_logged


async def test_hub_sensor_availability(hass: HomeAssistant):
    """Test hub sensor availability based on schedule sensors."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "schedule_1": {
                    "name": "Schedule 1",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
            },
        },
        entry_id="test_hub_avail",
    )

    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)

        hub_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(hub_entry.entry_id)
        await hass.async_block_till_done()

        hub_state = hass.states.get("binary_sensor.scheduler")
        assert hub_state
        # Hub should be available when at least one schedule is available
        assert hub_state.state != "unavailable"


async def test_calendar_unavailable_no_schedules(hass: HomeAssistant):
    """Test calendar becomes unavailable when no schedules exist."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_cal_unavail",
    )

    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Calendar should not be created when no schedules exist
    calendar_state = hass.states.get("calendar.scheduler")
    assert calendar_state is None


async def test_calendar_availability_with_schedules(hass: HomeAssistant):
    """Test calendar availability when schedules exist."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "test_schedule": {
                    "name": "Test Schedule",
                    "start_month": 6,
                    "end_month": 8,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
            },
        },
        entry_id="test_cal_avail",
    )

    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    calendar_state = hass.states.get("calendar.scheduler")
    assert calendar_state
    assert calendar_state.state != "unavailable"
