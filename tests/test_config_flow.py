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
            "start_month": "january",
            "end_month": "december",
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
        "start_month": "january",
        "end_month": "december",
        "start_day": 1,
        "end_day": 15,
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
            "start_month": "december",
            "end_month": "january",
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
                "start_month": "january",
                "end_month": "december",
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
            "start_month": "march",
            "end_month": "october",
            "start_day": 5,
            "end_day": 20,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data == {
        "name": "Updated Schedule",
        "schedule_type": "date",
        "start_month": "march",
        "end_month": "october",
        "start_day": 5,
        "end_day": 20,
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
            "start_month": "november",
            "end_month": "february",
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
                "start_month": "january",
                "end_month": "december",
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
            "start_month": "january",
            "end_month": "december",
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
    assert result3["data"]["start_day_of_week"] == "0"
    assert result3["data"]["end_day_of_week"] == "4"
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
            "start_month": "january",
            "end_month": "december",
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
            "start_month": "march",
            "end_month": "october",
            "start_day_of_week": "1",
            "end_day_of_week": "5",
            "start_week": 1,
            "end_week": 3,
        },
    )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data["schedule_type"] == "week"
    assert config_entry.data["start_day_of_week"] == "1"
    assert config_entry.data["end_day_of_week"] == "5"
    assert config_entry.data["start_week"] == 1
    assert config_entry.data["end_week"] == 3
