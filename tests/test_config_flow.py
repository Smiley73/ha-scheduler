"""Test the Scheduler config flow."""
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.scheduler.const import DOMAIN


async def test_form_create_hub(hass: HomeAssistant):
    """Test we can create the hub."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Scheduler"
    assert result2["data"] == {"schedules": {}}


async def test_form_already_configured(hass: HomeAssistant, empty_hub_entry):
    """Test we abort if hub already exists."""
    empty_hub_entry.add_to_hass(hass)
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_menu(hass: HomeAssistant, empty_hub_entry):
    """Test options flow shows menu."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    assert "add_schedule" in result["menu_options"]
    assert "edit_schedule" in result["menu_options"]
    assert "remove_schedule" in result["menu_options"]


async def test_options_add_schedule_date(hass: HomeAssistant, empty_hub_entry):
    """Test adding a date-based schedule."""
    empty_hub_entry.add_to_hass(hass)

    # Step 1: Menu
    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    
    # Step 2: Add schedule - name and type
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "add_schedule"
    
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )
    
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "date_config"
    
    # Step 3: Date configuration
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
        },
    )
    
    assert result4["type"] == FlowResultType.CREATE_ENTRY
    
    # Verify schedule was added
    schedules = empty_hub_entry.data["schedules"]
    assert len(schedules) == 1
    schedule_data = list(schedules.values())[0]
    assert schedule_data["name"] == "Test Schedule"
    assert schedule_data["schedule_type"] == "date"
    assert schedule_data["start_month"] == 1
    assert schedule_data["end_month"] == 12


async def test_options_add_schedule_week(hass: HomeAssistant, empty_hub_entry):
    """Test adding a week-based schedule."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Weekly Schedule",
            "schedule_type": "week",
        },
    )
    
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "week_config"
    
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "4",
            "start_week": 0,
            "end_week": 2,
        },
    )
    
    assert result4["type"] == FlowResultType.CREATE_ENTRY
    
    # Verify schedule was added
    schedules = empty_hub_entry.data["schedules"]
    assert len(schedules) == 1
    schedule_data = list(schedules.values())[0]
    assert schedule_data["name"] == "Weekly Schedule"
    assert schedule_data["schedule_type"] == "week"


async def test_options_edit_schedule(hass: HomeAssistant, hub_entry):
    """Test editing an existing schedule."""
    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "edit_schedule"},
    )
    
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "edit_schedule"
    
    # Select the schedule to edit
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "test_schedule_1"},
    )
    
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "date_config"
    
    # Update the schedule
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "3",
            "end_month": "10",
            "start_day": 5,
            "end_day": 20,
        },
    )
    
    assert result4["type"] == FlowResultType.CREATE_ENTRY
    
    # Verify schedule was updated
    schedule_data = hub_entry.data["schedules"]["test_schedule_1"]
    assert schedule_data["start_month"] == 3
    assert schedule_data["end_month"] == 10
    assert schedule_data["start_day"] == 5
    assert schedule_data["end_day"] == 20


async def test_options_remove_schedule(hass: HomeAssistant, hub_entry):
    """Test removing a schedule."""
    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_schedule"},
    )
    
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "remove_schedule"
    
    # Select the schedule to remove
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "test_schedule_1"},
    )
    
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    
    # Verify schedule was removed
    assert "test_schedule_1" not in hub_entry.data["schedules"]


async def test_options_edit_no_schedules(hass: HomeAssistant, empty_hub_entry):
    """Test editing when no schedules exist."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "edit_schedule"},
    )
    
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "no_schedules"


async def test_options_remove_no_schedules(hass: HomeAssistant, empty_hub_entry):
    """Test removing when no schedules exist."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_schedule"},
    )
    
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "no_schedules"


async def test_options_add_schedule_invalid_month_range(hass: HomeAssistant, empty_hub_entry):
    """Test adding schedule with invalid month range."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )
    
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "12",
            "end_month": "1",
            "start_day": 1,
            "end_day": 15,
        },
    )
    
    assert result4["type"] == FlowResultType.FORM
    assert result4["errors"] == {"base": "invalid_month_range"}


async def test_options_add_schedule_invalid_day_range(hass: HomeAssistant, empty_hub_entry):
    """Test adding schedule with invalid day range."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )
    
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 20,
            "end_day": 10,
        },
    )
    
    assert result4["type"] == FlowResultType.FORM
    assert result4["errors"] == {"base": "invalid_day_range"}


async def test_options_add_schedule_with_yaml(hass: HomeAssistant, empty_hub_entry):
    """Test adding schedule with additional YAML."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )
    
    valid_yaml = "enabled: true\ntimeout: 30"
    
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": valid_yaml,
        },
    )
    
    assert result4["type"] == FlowResultType.CREATE_ENTRY
    
    # Verify YAML was saved
    schedule_data = list(empty_hub_entry.data["schedules"].values())[0]
    assert schedule_data["additional_yaml"] == valid_yaml


async def test_options_add_schedule_invalid_yaml(hass: HomeAssistant, empty_hub_entry):
    """Test adding schedule with invalid YAML."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )
    
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )
    
    # Use truly invalid YAML (unclosed bracket)
    invalid_yaml = "key: [unclosed bracket"
    
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": invalid_yaml,
        },
    )
    
    assert result4["type"] == FlowResultType.FORM
    assert result4["errors"] == {"base": "invalid_yaml"}
