"""Test the Scheduler config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.scheduler.const import DOMAIN


async def test_form(hass: HomeAssistant):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "start_month": "january",
            "end_month": "december",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Schedule"
    assert result2["data"] == {
        "name": "Test Schedule",
        "start_month": "january",
        "end_month": "december",
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
            "start_month": "december",
            "end_month": "january",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_month_range"}


async def test_form_exception(hass: HomeAssistant):
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.scheduler.config_flow.validate_input",
        side_effect=Exception("Test exception"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test Schedule",
                "start_month": "january",
                "end_month": "december",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistant, config_entry):
    """Test options flow."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "start_month": "march",
            "end_month": "october",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.data == {
        "name": "Updated Schedule",
        "start_month": "march",
        "end_month": "october",
    }


async def test_options_flow_invalid_month_range(hass: HomeAssistant, config_entry):
    """Test options flow with invalid month range."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Updated Schedule",
            "start_month": "november",
            "end_month": "february",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_month_range"}


async def test_options_flow_exception(hass: HomeAssistant, config_entry):
    """Test options flow handles exceptions."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    with patch(
        "custom_components.scheduler.config_flow.validate_input",
        side_effect=Exception("Test exception"),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "name": "Updated Schedule",
                "start_month": "january",
                "end_month": "december",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
