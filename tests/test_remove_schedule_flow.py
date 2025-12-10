"""Test the remove schedule flow functionality."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_remove_schedule_flow_no_schedules(hass: HomeAssistant) -> None:
    """Test remove schedule flow when no schedules exist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select remove_schedule from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "remove_schedule"}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_schedules"


async def test_remove_schedule_flow_select_schedule(hass: HomeAssistant) -> None:
    """Test remove schedule flow - selecting a schedule."""
    schedules = {
        "schedule_1": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "uid": "schedule_1",
        },
        "schedule_2": {
            "name": "Winter Schedule",
            "schedule_type": "date",
            "uid": "schedule_2",
        },
        "schedule_3": {
            "name": "autumn schedule",  # lowercase for sorting test
            "schedule_type": "week",
            "uid": "schedule_3",
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedules},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select remove_schedule from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "remove_schedule"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "remove_schedule"

    # Verify schedule options are sorted case-insensitively
    schema = result["data_schema"].schema
    schedule_selector = schema["schedule_id"]
    options = schedule_selector.config["options"]

    # Should be sorted: autumn schedule, Summer Schedule, Winter Schedule
    assert len(options) == 3
    assert options[0]["label"] == "autumn schedule"
    assert options[1]["label"] == "Summer Schedule"
    assert options[2]["label"] == "Winter Schedule"


async def test_remove_schedule_flow_confirm_step(hass: HomeAssistant) -> None:
    """Test remove schedule flow - confirmation step."""
    schedules = {
        "schedule_1": {
            "name": "Test Schedule",
            "schedule_type": "date",
            "uid": "schedule_1",
        }
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedules},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select remove_schedule from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "remove_schedule"}
    )

    # Select schedule to remove
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"schedule_id": "schedule_1"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "remove_schedule"
    assert result["description_placeholders"]["schedule_name"] == "Test Schedule"
    assert result["description_placeholders"]["schedule_type"] == "date"


async def test_remove_schedule_flow_confirm_removal(hass: HomeAssistant) -> None:
    """Test remove schedule flow - confirming removal."""
    schedules = {
        "schedule_1": {
            "name": "Test Schedule",
            "schedule_type": "date",
            "uid": "schedule_1",
        },
        "schedule_2": {
            "name": "Keep Schedule",
            "schedule_type": "week",
            "uid": "schedule_2",
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedules},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select remove_schedule from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "remove_schedule"}
    )

    # Select schedule to remove
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"schedule_id": "schedule_1"}
    )

    # Confirm removal
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"confirm": True}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "schedule_1" not in result["data"]["schedules"]
    assert "schedule_2" in result["data"]["schedules"]


async def test_remove_schedule_flow_cancel_removal(hass: HomeAssistant) -> None:
    """Test remove schedule flow - canceling removal."""
    schedules = {
        "schedule_1": {
            "name": "Test Schedule",
            "schedule_type": "date",
            "uid": "schedule_1",
        }
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedules},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select remove_schedule from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "remove_schedule"}
    )

    # Select schedule to remove
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"schedule_id": "schedule_1"}
    )

    # Cancel removal
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"confirm": False}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_confirmed"
