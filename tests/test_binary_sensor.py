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


async def test_binary_sensor_month_wrap_around(hass: HomeAssistant):
    """Test binary sensor with month wrap-around (Nov-Feb)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Winter Schedule",
        data={
            "name": "Winter Schedule",
            "start_month": 11,  # November
            "end_month": 2,     # February
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 28,
        },
        entry_id="test_winter",
        unique_id="test_winter_unique",
    )
    
    # Test date in December (should be active)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 12, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.winter_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"


async def test_binary_sensor_month_wrap_around_outside(hass: HomeAssistant):
    """Test binary sensor with month wrap-around outside range."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Winter Schedule",
        data={
            "name": "Winter Schedule",
            "start_month": 11,  # November
            "end_month": 2,     # February
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 28,
        },
        entry_id="test_winter2",
        unique_id="test_winter_unique2",
    )
    
    # Test date in June (should be inactive)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.winter_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "off"


async def test_binary_sensor_week_wrap_around_days(hass: HomeAssistant):
    """Test binary sensor with day of week wrap-around (Fri-Mon)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Weekend Schedule",
        data={
            "name": "Weekend Schedule",
            "schedule_type": "week",
            "start_month": 1,
            "end_month": 12,
            "start_day_of_week": 4,  # Friday
            "end_day_of_week": 0,    # Monday (wrap around)
            "start_week": 0,
            "end_week": 4,
        },
        entry_id="test_weekend",
        unique_id="test_weekend_unique",
    )
    
    # Test on Saturday (should be active)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 7)  # Saturday
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.weekend_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"


async def test_binary_sensor_week_outside_day_range(hass: HomeAssistant):
    """Test binary sensor outside day of week range."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Weekday Schedule",
        data={
            "name": "Weekday Schedule",
            "schedule_type": "week",
            "start_month": 1,
            "end_month": 12,
            "start_day_of_week": 0,  # Monday
            "end_day_of_week": 4,    # Friday
            "start_week": 0,
            "end_week": 4,
        },
        entry_id="test_weekday",
        unique_id="test_weekday_unique",
    )
    
    # Test on Sunday (should be inactive)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 8)  # Sunday
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.weekday_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "off"


async def test_binary_sensor_week_outside_week_range(hass: HomeAssistant):
    """Test binary sensor outside week of month range."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="First Week Schedule",
        data={
            "name": "First Week Schedule",
            "schedule_type": "week",
            "start_month": 1,
            "end_month": 12,
            "start_day_of_week": 0,  # Monday
            "end_day_of_week": 6,    # Sunday
            "start_week": 0,         # First week only
            "end_week": 0,
        },
        entry_id="test_first_week",
        unique_id="test_first_week_unique",
    )
    
    # Test on third week (June 16, 2025 is a Monday in the 3rd week)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 16)  # Monday, 3rd week
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.first_week_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "off"


async def test_binary_sensor_start_day_boundary(hass: HomeAssistant):
    """Test binary sensor on start day boundary."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mid Month Schedule",
        data={
            "name": "Mid Month Schedule",
            "start_month": 6,
            "end_month": 6,
            "schedule_type": "date",
            "start_day": 15,
            "end_day": 20,
        },
        entry_id="test_mid_month",
        unique_id="test_mid_month_unique",
    )
    
    # Test on start day (should be active)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.mid_month_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"


async def test_binary_sensor_before_start_day(hass: HomeAssistant):
    """Test binary sensor before start day in start month."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mid Month Schedule",
        data={
            "name": "Mid Month Schedule",
            "start_month": 6,
            "end_month": 6,
            "schedule_type": "date",
            "start_day": 15,
            "end_day": 20,
        },
        entry_id="test_before_start",
        unique_id="test_before_start_unique",
    )
    
    # Test before start day (should be inactive)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 10)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.mid_month_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "off"


async def test_binary_sensor_after_end_day(hass: HomeAssistant):
    """Test binary sensor after end day in end month."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mid Month Schedule",
        data={
            "name": "Mid Month Schedule",
            "start_month": 6,
            "end_month": 6,
            "schedule_type": "date",
            "start_day": 15,
            "end_day": 20,
        },
        entry_id="test_after_end",
        unique_id="test_after_end_unique",
    )
    
    # Test after end day (should be inactive)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 25)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.mid_month_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "off"


async def test_binary_sensor_multi_month_middle_month(hass: HomeAssistant):
    """Test binary sensor in middle month of multi-month range."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Summer Schedule",
        data={
            "name": "Summer Schedule",
            "start_month": 5,   # May
            "end_month": 8,     # August
            "schedule_type": "date",
            "start_day": 15,
            "end_day": 20,
        },
        entry_id="test_summer",
        unique_id="test_summer_unique",
    )
    
    # Test in July (middle month, any day should be active)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 7, 5)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.summer_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"


async def test_binary_sensor_update_callback(hass: HomeAssistant):
    """Test binary sensor update callback."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from datetime import timedelta
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Schedule",
        data={
            "name": "Test Schedule",
            "start_month": 6,
            "end_month": 6,
            "schedule_type": "date",
            "start_day": 15,
            "end_day": 20,
        },
        entry_id="test_callback",
        unique_id="test_callback_unique",
    )
    
    # Start with date in range
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 16)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.test_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"
        
        # Simulate time passing to outside range
        mock_datetime.now.return_value = datetime(2025, 6, 25)
        
        # Trigger update by advancing time
        import homeassistant.util.dt as dt_util
        future = dt_util.utcnow() + timedelta(hours=1)
        async with hass.timeout.async_timeout(5):
            hass.bus.async_fire("time_changed", {"now": future})
            await hass.async_block_till_done()


async def test_binary_sensor_last_week_of_month(hass: HomeAssistant):
    """Test binary sensor on last week of month."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Last Week Schedule",
        data={
            "name": "Last Week Schedule",
            "schedule_type": "week",
            "start_month": 1,
            "end_month": 12,
            "start_day_of_week": 0,  # Monday
            "end_day_of_week": 6,    # Sunday
            "start_week": 4,         # Last week
            "end_week": 4,
        },
        entry_id="test_last_week",
        unique_id="test_last_week_unique",
    )
    
    # Test on June 30, 2025 (Monday, last week of month)
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 30)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.last_week_schedule"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "on"


async def test_binary_sensor_attributes_week_schedule(hass: HomeAssistant):
    """Test binary sensor attributes for week-based schedule."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Week Attrs Test",
        data={
            "name": "Week Attrs Test",
            "schedule_type": "week",
            "start_month": 3,
            "end_month": 9,
            "start_day_of_week": 1,
            "end_day_of_week": 5,
            "start_week": 1,
            "end_week": 3,
        },
        entry_id="test_week_attrs",
        unique_id="test_week_attrs_unique",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 10)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.week_attrs_test"
        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["schedule_type"] == "week"
        assert state.attributes["start_month"] == 3
        assert state.attributes["end_month"] == 9
        assert state.attributes["start_day_of_week"] == 1
        assert state.attributes["end_day_of_week"] == 5
        assert state.attributes["start_week"] == 1
        assert state.attributes["end_week"] == 3
        # Should not have date-based attributes
        assert "start_day" not in state.attributes
        assert "end_day" not in state.attributes


async def test_binary_sensor_with_additional_yaml_dict(hass: HomeAssistant):
    """Test binary sensor with additional YAML config as dictionary."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Config Test",
        data={
            "name": "Config Test",
            "start_month": 1,
            "end_month": 12,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 31,
            "additional_yaml": "enabled: true\ntimeout: 30\nmode: advanced",
        },
        entry_id="test_config_dict",
        unique_id="test_config_dict_unique",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.config_test"
        state = hass.states.get(entity_id)
        assert state
        assert "config" in state.attributes
        assert state.attributes["config"]["enabled"] is True
        assert state.attributes["config"]["timeout"] == 30
        assert state.attributes["config"]["mode"] == "advanced"


async def test_binary_sensor_with_additional_yaml_list(hass: HomeAssistant):
    """Test binary sensor with additional YAML config as list."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="List Config Test",
        data={
            "name": "List Config Test",
            "start_month": 1,
            "end_month": 12,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 31,
            "additional_yaml": "- item1\n- item2\n- item3",
        },
        entry_id="test_config_list",
        unique_id="test_config_list_unique",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.list_config_test"
        state = hass.states.get(entity_id)
        assert state
        assert "config" in state.attributes
        assert state.attributes["config"] == ["item1", "item2", "item3"]


async def test_binary_sensor_with_empty_additional_yaml(hass: HomeAssistant):
    """Test binary sensor with empty additional YAML."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Empty Config Test",
        data={
            "name": "Empty Config Test",
            "start_month": 1,
            "end_month": 12,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 31,
            "additional_yaml": "",
        },
        entry_id="test_empty_config",
        unique_id="test_empty_config_unique",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.empty_config_test"
        state = hass.states.get(entity_id)
        assert state
        # Should not have config attribute when additional_yaml is empty
        assert "config" not in state.attributes


async def test_binary_sensor_with_nested_yaml_config(hass: HomeAssistant):
    """Test binary sensor with nested YAML config."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    nested_yaml = """
database:
  host: localhost
  port: 5432
  credentials:
    username: admin
    password: secret
features:
  - feature1
  - feature2
settings:
  enabled: true
  timeout: 60
"""
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Nested Config Test",
        data={
            "name": "Nested Config Test",
            "start_month": 1,
            "end_month": 12,
            "schedule_type": "week",
            "start_day_of_week": 0,
            "end_day_of_week": 6,
            "start_week": 0,
            "end_week": 4,
            "additional_yaml": nested_yaml.strip(),
        },
        entry_id="test_nested_config",
        unique_id="test_nested_config_unique",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.nested_config_test"
        state = hass.states.get(entity_id)
        assert state
        assert "config" in state.attributes
        assert state.attributes["config"]["database"]["host"] == "localhost"
        assert state.attributes["config"]["database"]["port"] == 5432
        assert state.attributes["config"]["database"]["credentials"]["username"] == "admin"
        assert state.attributes["config"]["features"] == ["feature1", "feature2"]
        assert state.attributes["config"]["settings"]["enabled"] is True
        assert state.attributes["config"]["settings"]["timeout"] == 60


async def test_binary_sensor_with_invalid_yaml_config(hass: HomeAssistant):
    """Test binary sensor with invalid YAML config (should be ignored)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Invalid Config Test",
        data={
            "name": "Invalid Config Test",
            "start_month": 1,
            "end_month": 12,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 31,
            "additional_yaml": "invalid: yaml: structure: [unclosed",
        },
        entry_id="test_invalid_config",
        unique_id="test_invalid_config_unique",
    )
    
    with patch("custom_components.scheduler.binary_sensor.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 6, 15)
        
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "binary_sensor.invalid_config_test"
        state = hass.states.get(entity_id)
        assert state
        # Should not have config attribute when YAML is invalid
        assert "config" not in state.attributes
