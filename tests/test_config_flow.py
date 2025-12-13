"""Test the Scheduler config flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _create_test_entry(title="Test Scheduler", schedules=None):
    """Create a test config entry with service-based structure."""
    if schedules is None:
        schedules = {}

    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={"scheduler_name": title},
        options={
            "services": {
                "default": {
                    "name": title,
                    "schedules": schedules,
                    "configuration": {},
                }
            }
        },
        version=2,  # Set version to 2 to avoid migration
        minor_version=1,
    )


def _get_schedules_from_entry(entry):
    """Get schedules from service-based entry structure."""
    return entry.options.get("services", {}).get("default", {}).get("schedules", {})


def _get_configuration_from_entry(entry):
    """Get configuration from service-based entry structure."""
    return entry.options.get("services", {}).get("default", {}).get("configuration", {})


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result.get("errors") is None or result["errors"] == {}

    with patch(
        "custom_components.ha_scheduler.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"scheduler_name": "Test Scheduler"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Scheduler"
    assert result2["data"] == {"scheduler_name": "Test Scheduler"}
    assert result2["options"] == {
        "services": {
            "default": {
                "name": "Test Scheduler",
                "schedules": {},
                "configuration": {},
            }
        }
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow_add_date_schedule(hass: HomeAssistant) -> None:
    """Test adding a date-based schedule via options flow."""
    entry = _create_test_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Initialize options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert "add_schedule" in result["menu_options"]

    # Select add_schedule
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_schedule"

    # Select date type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_type": "date"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_date"

    # Configure date schedule
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Summer Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify schedule was added
    schedules = _get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["name"] == "Summer Schedule"
    assert schedule["schedule_type"] == "date"
    assert schedule["start_month"] == 6
    assert schedule["start_day"] == 1


async def test_options_flow_add_week_schedule(hass: HomeAssistant) -> None:
    """Test adding a week-based schedule via options flow."""
    entry = _create_test_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_type": "week"},
    )
    assert result["step_id"] == "configure_week"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Week Schedule",
            "start_month": "3",
            "start_week": "0_partial",  # Updated to new format
            "start_day_of_week": "0",
            "end_month": "6",
            "end_week": "4",  # Last week doesn't need type suffix
            "end_day_of_week": "4",
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    schedules = _get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["name"] == "Week Schedule"
    assert schedule["schedule_type"] == "week"


async def test_options_flow_add_nth_day_schedule(hass: HomeAssistant) -> None:
    """Test adding an nth-day schedule via options flow."""
    entry = _create_test_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_type": "nth-day"},
    )
    assert result["step_id"] == "configure_nth_day"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Nth Day Schedule",
            "month": "3",
            "occurrence": "1",
            "day_of_week": "1",
            "start_offset": 2,
            "end_offset": 3,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    schedules = _get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["name"] == "Nth Day Schedule"
    assert schedule["schedule_type"] == "nth-day"
    assert schedule["start_offset"] == 2
    assert schedule["end_offset"] == 3


async def test_options_flow_default_configuration(hass: HomeAssistant) -> None:
    """Test setting default configuration."""
    entry = _create_test_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "default_configuration"},
    )
    assert result["step_id"] == "default_configuration"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"configuration": "key: value\nother: 123"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    config = _get_configuration_from_entry(entry)
    assert config == {"key": "value", "other": 123}


async def test_options_flow_invalid_yaml(hass: HomeAssistant) -> None:
    """Test invalid YAML in configuration."""
    entry = _create_test_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_type": "date"},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test",
            "start_month": "1",
            "start_day": 1,
            "end_month": "12",
            "end_day": 31,
            "configuration": "invalid: yaml: [",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert "base" in result["errors"]


async def test_options_flow_edit_schedule_with_configuration(
    hass: HomeAssistant,
) -> None:
    """Test editing a schedule with configuration displays YAML correctly."""
    schedules = {
        "test-id": {
            "uid": "test-id",
            "name": "Test Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "configuration": {"color": "red", "brightness": 75},
        }
    }
    entry = _create_test_entry(schedules=schedules)
    entry.add_to_hass(hass)

    # Start options flow and navigate to edit_schedule
    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"show_advanced_options": False}
    )
    assert result["type"] == FlowResultType.MENU

    # Navigate to edit schedule step
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "edit_schedule"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit_schedule"

    # Select the schedule to edit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "test-id"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_date"

    # Configuration field should be present
    schema = result["data_schema"].schema
    config_field_exists = any(str(key) == "configuration" for key in schema)
    assert config_field_exists


async def test_form_duplicate_scheduler_name(hass: HomeAssistant) -> None:
    """Test that duplicate scheduler names are rejected."""
    # Create first scheduler
    entry1 = _create_test_entry("My Scheduler")
    entry1.add_to_hass(hass)

    # Try to create second scheduler with same name
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"scheduler_name": "My Scheduler"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"scheduler_name": "duplicate_scheduler_name"}


async def test_form_duplicate_scheduler_name_case_insensitive(
    hass: HomeAssistant,
) -> None:
    """Test that duplicate scheduler names are rejected (case insensitive)."""
    # Create first scheduler
    entry1 = _create_test_entry("My Scheduler")
    entry1.add_to_hass(hass)

    # Try to create second scheduler with same name but different case
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"scheduler_name": "my scheduler"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"scheduler_name": "duplicate_scheduler_name"}


async def test_add_schedule_duplicate_name(hass: HomeAssistant) -> None:
    """Test that duplicate schedule names are rejected."""
    schedules = {
        "existing-id": {
            "uid": "existing-id",
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
        }
    }
    entry = _create_test_entry(schedules=schedules)
    entry.add_to_hass(hass)

    # Try to add another schedule with the same name
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "add_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_type": "date"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Summer Schedule",
            "start_month": "9",
            "start_day": 1,
            "end_month": "11",
            "end_day": 30,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {
        "name": "A schedule with this name already exists. Please choose a different name."
    }


async def test_edit_schedule_keep_same_name(hass: HomeAssistant) -> None:
    """Test that editing a schedule can keep the same name."""
    schedules = {
        "test-id": {
            "uid": "test-id",
            "name": "My Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
        }
    }
    entry = _create_test_entry(schedules=schedules)
    entry.add_to_hass(hass)

    # Edit the schedule keeping the same name
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "edit_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "test-id"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "My Schedule",  # Same name
            "start_month": "6",
            "start_day": 1,
            "end_month": "9",  # Changed end month
            "end_day": 30,
        },
    )

    # Should succeed
    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Get updated schedules from the service structure
    services = result["data"]["services"]
    updated_schedule = services["default"]["schedules"]["test-id"]
    assert updated_schedule["name"] == "My Schedule"
    assert updated_schedule["end_month"] == 9


async def test_edit_schedule_remove_configuration(hass: HomeAssistant) -> None:
    """Test that editing a schedule and emptying configuration removes it."""
    schedules = {
        "test-id": {
            "uid": "test-id",
            "name": "Test Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "configuration": {"color": "red", "brightness": 75},
        }
    }
    entry = _create_test_entry(schedules=schedules)
    entry.add_to_hass(hass)

    # Edit the schedule and remove configuration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "edit_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "test-id"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",  # Empty configuration
        },
    )

    # Should succeed and configuration should be removed
    assert result["type"] == FlowResultType.CREATE_ENTRY
    services = result["data"]["services"]
    updated_schedule = services["default"]["schedules"]["test-id"]
    assert updated_schedule["name"] == "Test Schedule"
    assert "configuration" not in updated_schedule
