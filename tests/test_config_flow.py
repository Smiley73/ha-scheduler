"""Test the Scheduler config flow."""
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.scheduler.const import DOMAIN


async def test_form(hass: HomeAssistant):
    """Test we get the form."""
    # Step 1: Name and type selection
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: Date configuration
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "date_config"

    # Step 3: Submit date details
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Test Schedule"
    assert result3["data"] == {
        "name": "Test Schedule",
        "schedule_type": "date",
        "start_month": 1,
        "end_month": 12,
        "start_day": 1,
        "end_day": 15,
        "additional_yaml": "",
    }


async def test_form_invalid_month_range(hass: HomeAssistant):
    """Test we handle invalid month range."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "12",
            "end_month": "1",
            "start_day": 1,
            "end_day": 15,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_month_range"}


async def test_form_exception(hass: HomeAssistant):
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    with patch(
        "custom_components.scheduler.config_flow.validate_input",
        side_effect=Exception("Test exception"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "start_month": "1",
                "end_month": "12",
                "start_day": 1,
                "end_day": 15,
            },
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistant, config_entry):
    """Test options flow."""
    config_entry.add_to_hass(hass)

    # Step 1: Name and type selection
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Step 2: Date configuration
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "date",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "date_config"

    # Step 3: Submit date details
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "3",
            "end_month": "10",
            "start_day": 5,
            "end_day": 20,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data == {
        "name": "Updated Schedule",
        "schedule_type": "date",
        "start_month": 3,
        "end_month": 10,
        "start_day": 5,
        "end_day": 20,
        "additional_yaml": "",
    }


async def test_options_flow_invalid_month_range(hass: HomeAssistant, config_entry):
    """Test options flow with invalid month range."""
    config_entry.add_to_hass(hass)

    # Step 1: Name and type selection
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Step 2: Date configuration
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "date",
        },
    )

    # Step 3: Submit invalid month range
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "11",
            "end_month": "2",
            "start_day": 1,
            "end_day": 15,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_month_range"}


async def test_options_flow_exception(hass: HomeAssistant, config_entry):
    """Test options flow handles exceptions."""
    config_entry.add_to_hass(hass)

    # Step 1: Name and type selection
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Step 2: Date configuration
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "date",
        },
    )

    # Step 3: Submit with exception
    with patch(
        "custom_components.scheduler.config_flow.validate_input",
        side_effect=Exception("Test exception"),
    ):
        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "start_month": "1",
                "end_month": "12",
                "start_day": 1,
                "end_day": 15,
            },
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}


async def test_form_week_schedule(hass: HomeAssistant):
    """Test we can create a week-based schedule."""
    # Step 1: Name and type selection
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Step 2: Week configuration
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Weekly Schedule",
            "schedule_type": "week",
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "week_config"

    # Step 3: Submit week details
    result3 = await hass.config_entries.flow.async_configure(
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
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Weekly Schedule"
    assert result3["data"]["schedule_type"] == "week"
    assert result3["data"]["start_day_of_week"] == 0
    assert result3["data"]["end_day_of_week"] == 4
    assert result3["data"]["start_week"] == 0
    assert result3["data"]["end_week"] == 2


async def test_form_invalid_day_range(hass: HomeAssistant):
    """Test we handle invalid day range."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 20,
            "end_day": 10,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_day_range"}


async def test_options_flow_week_schedule(hass: HomeAssistant, config_entry):
    """Test options flow with week-based schedule."""
    config_entry.add_to_hass(hass)

    # Step 1: Name and type selection
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Step 2: Week configuration
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Weekly Schedule",
            "schedule_type": "week",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "week_config"

    # Step 3: Submit week details
    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "3",
            "end_month": "10",
            "start_day_of_week": "1",
            "end_day_of_week": "5",
            "start_week": 1,
            "end_week": 3,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data["schedule_type"] == "week"
    assert config_entry.data["start_day_of_week"] == 1
    assert config_entry.data["end_day_of_week"] == 5
    assert config_entry.data["start_week"] == 1
    assert config_entry.data["end_week"] == 3


async def test_form_invalid_week_range(hass: HomeAssistant):
    """Test we handle invalid week range."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "week",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 3,
            "end_week": 1,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_week_range"}


async def test_form_boundary_days(hass: HomeAssistant):
    """Test boundary values for days (1 and 31)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Boundary Test",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "1",
            "start_day": 1,
            "end_day": 31,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["start_day"] == 1
    assert result3["data"]["end_day"] == 31


async def test_form_boundary_weeks(hass: HomeAssistant):
    """Test boundary values for weeks (0 and 4)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Week Boundary Test",
            "schedule_type": "week",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 0,
            "end_week": 4,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["start_week"] == 0
    assert result3["data"]["end_week"] == 4


async def test_form_same_month_range(hass: HomeAssistant):
    """Test schedule within the same month."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Same Month",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "6",
            "end_month": "6",
            "start_day": 10,
            "end_day": 20,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["start_month"] == 6
    assert result3["data"]["end_month"] == 6


async def test_options_flow_invalid_week_range(hass: HomeAssistant, config_entry):
    """Test options flow with invalid week range."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "week",
        },
    )

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 4,
            "end_week": 0,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_week_range"}


async def test_options_flow_invalid_day_range(hass: HomeAssistant, config_entry):
    """Test options flow with invalid day range."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "1",
            "end_month": "12",
            "start_day": 25,
            "end_day": 5,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_day_range"}


async def test_form_week_exception(hass: HomeAssistant):
    """Test we handle exceptions in week-based schedule."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "week",
        },
    )

    with patch(
        "custom_components.scheduler.config_flow.validate_input",
        side_effect=Exception("Test exception"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "start_month": "1",
                "end_month": "12",
                "start_day_of_week": "0",
                "end_day_of_week": "6",
                "start_week": 0,
                "end_week": 2,
            },
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}


async def test_options_flow_week_exception(hass: HomeAssistant, config_entry):
    """Test options flow handles exceptions in week-based schedule."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "week",
        },
    )

    with patch(
        "custom_components.scheduler.config_flow.validate_input",
        side_effect=Exception("Test exception"),
    ):
        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "start_month": "1",
                "end_month": "12",
                "start_day_of_week": "0",
                "end_day_of_week": "6",
                "start_week": 0,
                "end_week": 2,
            },
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}


async def test_form_invalid_day_of_week_range(hass: HomeAssistant):
    """Test we handle invalid day of week range in same-day scenario."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "week",
        },
    )

    # Note: Day of week wrap-around is actually valid (e.g., Fri-Mon)
    # This test ensures the validation doesn't reject valid wrap-around ranges
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "5",  # Saturday
            "end_day_of_week": "1",    # Tuesday (wrap around)
            "start_week": 0,
            "end_week": 4,
        },
    )

    # This should succeed as wrap-around is valid
    assert result3["type"] == FlowResultType.CREATE_ENTRY


async def test_form_single_day_schedule(hass: HomeAssistant):
    """Test schedule for a single day."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Single Day",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "6",
            "end_month": "6",
            "start_day": 15,
            "end_day": 15,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["start_day"] == 15
    assert result3["data"]["end_day"] == 15


async def test_form_year_round_schedule(hass: HomeAssistant):
    """Test year-round schedule (all months, all days)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Year Round",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 31,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["start_month"] == 1
    assert result3["data"]["end_month"] == 12


async def test_options_flow_change_schedule_type(hass: HomeAssistant):
    """Test changing schedule type from date to week in options flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    
    # Start with date-based schedule
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Schedule",
        data={
            "name": "Test Schedule",
            "start_month": 1,
            "end_month": 12,
            "schedule_type": "date",
            "start_day": 1,
            "end_day": 15,
        },
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
    
    config_entry.add_to_hass(hass)

    # Change to week-based
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "week",
        },
    )

    assert result2["step_id"] == "week_config"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "4",
            "start_week": 0,
            "end_week": 2,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data["schedule_type"] == "week"
    # Old date fields should be removed
    assert "start_day" not in config_entry.data
    assert "end_day" not in config_entry.data


async def test_form_last_day_of_month(hass: HomeAssistant):
    """Test schedule ending on day 31."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "End of Month",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 25,
            "end_day": 31,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["end_day"] == 31


async def test_form_single_week_schedule(hass: HomeAssistant):
    """Test schedule for a single week."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Single Week",
            "schedule_type": "week",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "6",
            "end_month": "6",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 2,
            "end_week": 2,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["start_week"] == 2
    assert result3["data"]["end_week"] == 2


async def test_options_flow_single_day_schedule(hass: HomeAssistant, config_entry):
    """Test options flow with single day schedule."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Single Day Schedule",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "7",
            "end_month": "7",
            "start_day": 4,
            "end_day": 4,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data["start_day"] == 4
    assert config_entry.data["end_day"] == 4


async def test_form_date_with_valid_yaml(hass: HomeAssistant):
    """Test date schedule with valid additional YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    valid_yaml = "key1: value1\nkey2:\n  nested: value2\nlist:\n  - item1\n  - item2"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": valid_yaml,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["additional_yaml"] == valid_yaml


async def test_form_date_with_invalid_yaml(hass: HomeAssistant):
    """Test date schedule with invalid YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    invalid_yaml = """
key1: value1
  invalid indentation
key2: [unclosed bracket
"""

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": invalid_yaml,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}


async def test_form_date_with_empty_yaml(hass: HomeAssistant):
    """Test date schedule with empty YAML (should be valid)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": "",
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["additional_yaml"] == ""


async def test_form_week_with_valid_yaml(hass: HomeAssistant):
    """Test week schedule with valid additional YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Weekly Schedule",
            "schedule_type": "week",
        },
    )

    valid_yaml = "config:\n  enabled: true\n  priority: high"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "4",
            "start_week": 0,
            "end_week": 2,
            "additional_yaml": valid_yaml,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["additional_yaml"] == valid_yaml


async def test_form_week_with_invalid_yaml(hass: HomeAssistant):
    """Test week schedule with invalid YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Weekly Schedule",
            "schedule_type": "week",
        },
    )

    invalid_yaml = """
key: value
  bad: indentation
"""

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "4",
            "start_week": 0,
            "end_week": 2,
            "additional_yaml": invalid_yaml,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}


async def test_options_flow_date_with_valid_yaml(hass: HomeAssistant, config_entry):
    """Test options flow date schedule with valid YAML."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "date",
        },
    )

    valid_yaml = "option1: value1\noption2: value2"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "3",
            "end_month": "10",
            "start_day": 5,
            "end_day": 20,
            "additional_yaml": valid_yaml,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data["additional_yaml"] == valid_yaml


async def test_options_flow_date_with_invalid_yaml(hass: HomeAssistant, config_entry):
    """Test options flow date schedule with invalid YAML."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "date",
        },
    )

    invalid_yaml = "{ invalid: yaml: structure"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "3",
            "end_month": "10",
            "start_day": 5,
            "end_day": 20,
            "additional_yaml": invalid_yaml,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}


async def test_options_flow_week_with_valid_yaml(hass: HomeAssistant, config_entry):
    """Test options flow week schedule with valid YAML."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Weekly Schedule",
            "schedule_type": "week",
        },
    )

    valid_yaml = "settings:\n  mode: advanced\n  timeout: 30"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "3",
            "end_month": "10",
            "start_day_of_week": "1",
            "end_day_of_week": "5",
            "start_week": 1,
            "end_week": 3,
            "additional_yaml": valid_yaml,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data["additional_yaml"] == valid_yaml


async def test_options_flow_week_with_invalid_yaml(hass: HomeAssistant, config_entry):
    """Test options flow week schedule with invalid YAML."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Weekly Schedule",
            "schedule_type": "week",
        },
    )

    # Invalid YAML with improper indentation
    invalid_yaml = "key: value\n  bad_indent: value2"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "3",
            "end_month": "10",
            "start_day_of_week": "1",
            "end_day_of_week": "5",
            "start_week": 1,
            "end_week": 3,
            "additional_yaml": invalid_yaml,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}


async def test_form_date_with_whitespace_only_yaml(hass: HomeAssistant):
    """Test date schedule with whitespace-only YAML (should be valid)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": "   \n  \n  ",
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY


async def test_form_week_with_complex_valid_yaml(hass: HomeAssistant):
    """Test week schedule with complex valid YAML structure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Complex Schedule",
            "schedule_type": "week",
        },
    )

    complex_yaml = "database:\n  host: localhost\n  port: 5432\n  credentials:\n    username: admin\n    password: secret\nfeatures:\n  - feature1\n  - feature2\n  - feature3\nsettings:\n  enabled: true\n  timeout: 60\n  retries: 3"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 0,
            "end_week": 4,
            "additional_yaml": complex_yaml,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["additional_yaml"] == complex_yaml


async def test_form_date_with_simple_string_yaml(hass: HomeAssistant):
    """Test date schedule with simple string YAML (should be invalid)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    # Simple string is not a valid YAML structure
    simple_string = "just a simple string"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": simple_string,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}


async def test_form_week_with_simple_number_yaml(hass: HomeAssistant):
    """Test week schedule with simple number YAML (should be invalid)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "week",
        },
    )

    # Simple number is not a valid YAML structure
    simple_number = "42"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 0,
            "end_week": 4,
            "additional_yaml": simple_number,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}


async def test_options_flow_date_with_simple_string_yaml(hass: HomeAssistant, config_entry):
    """Test options flow date schedule with simple string YAML (should be invalid)."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "schedule_type": "date",
        },
    )

    # Simple string is not a valid YAML structure
    simple_string = "hello world"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "3",
            "end_month": "10",
            "start_day": 5,
            "end_day": 20,
            "additional_yaml": simple_string,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}


async def test_form_date_with_valid_list_yaml(hass: HomeAssistant):
    """Test date schedule with valid list YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    # Valid list structure
    list_yaml = "- item1\n- item2\n- item3"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": list_yaml,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"]["additional_yaml"] == list_yaml


async def test_form_week_with_boolean_yaml(hass: HomeAssistant):
    """Test week schedule with simple boolean YAML (should be invalid)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "week",
        },
    )

    # Simple boolean is not a valid YAML structure
    simple_bool = "true"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 0,
            "end_week": 4,
            "additional_yaml": simple_bool,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}


async def test_form_date_with_null_yaml(hass: HomeAssistant):
    """Test date schedule with null YAML (should be invalid)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "schedule_type": "date",
        },
    )

    # null is not a valid YAML structure
    null_yaml = "null"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "12",
            "start_day": 1,
            "end_day": 15,
            "additional_yaml": null_yaml,
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_yaml"}
