"""Test adding schedules through the complete flow."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_complete_add_date_schedule_flow(hass: HomeAssistant) -> None:
    """Test the complete flow of adding a date schedule."""
    # Setup integration
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Start options flow
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

    # Configure the schedule
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )

    # Should complete successfully
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Wait for the update to propagate
    await hass.async_block_till_done()

    # Verify the schedule was saved - check the updated entry
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)

    print(f"\nEntry options after add: {updated_entry.options}")

    # Check both legacy and new structure
    legacy_schedules = updated_entry.options.get("schedules", {})
    services = updated_entry.options.get("services", {})

    if services:
        # New service-based structure
        default_service = services.get("default", {})
        schedules = default_service.get("schedules", {})
    else:
        # Legacy structure
        schedules = legacy_schedules

    print(f"Schedules after add: {schedules}")
    print(f"Number of schedules: {len(schedules)}")

    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["name"] == "Test Schedule"
    assert schedule["schedule_type"] == "date"
    assert schedule["start_month"] == 6
    assert schedule["start_day"] == 1
    assert schedule["end_month"] == 8
    assert schedule["end_day"] == 31
    assert "uid" in schedule


async def test_add_multiple_schedules(hass: HomeAssistant) -> None:
    """Test adding multiple schedules."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add first schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Schedule 1",
            "start_month": "1",
            "start_day": 1,
            "end_month": "3",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify first schedule
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    services = updated_entry.options.get("services", {})
    if services:
        schedules = services.get("default", {}).get("schedules", {})
    else:
        schedules = updated_entry.options.get("schedules", {})
    print(f"\nSchedules after first add: {schedules}")
    assert len(schedules) == 1

    # Add second schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Schedule 2",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify both schedules
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    services = updated_entry.options.get("services", {})
    if services:
        schedules = services.get("default", {}).get("schedules", {})
    else:
        schedules = updated_entry.options.get("schedules", {})
    print(f"\nSchedules after second add: {schedules}")
    assert len(schedules) == 2

    names = [s["name"] for s in schedules.values()]
    assert "Schedule 1" in names
    assert "Schedule 2" in names


async def test_add_schedule_with_overlap_error(hass: HomeAssistant) -> None:
    """Test that overlapping schedules are rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add first schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Schedule 1",
            "start_month": "3",
            "start_day": 1,
            "end_month": "6",
            "end_day": 30,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Try to add overlapping schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Schedule 2",
            "start_month": "5",  # Overlaps with Schedule 1
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )

    # Should show error
    assert result["type"] == FlowResultType.FORM
    assert "errors" in result
    assert "base" in result["errors"]
    assert "Schedule 1" in result["errors"]["base"]

    # Verify only one schedule exists
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    services = updated_entry.options.get("services", {})
    if services:
        schedules = services.get("default", {}).get("schedules", {})
    else:
        schedules = updated_entry.options.get("schedules", {})
    assert len(schedules) == 1
