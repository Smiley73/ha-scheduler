"""Test schedule persistence through config entries."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _create_service_entry(title="Test Scheduler", schedules=None, configuration=None):
    """Create a test config entry with service-based structure."""
    if schedules is None:
        schedules = {}
    if configuration is None:
        configuration = {}

    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={"scheduler_name": title},
        options={
            "services": {
                "default": {
                    "name": title,
                    "schedules": schedules,
                    "configuration": configuration,
                }
            }
        },
        version=2,  # Set version to 2 to avoid migration
        minor_version=1,
    )


def _get_schedules_from_entry(entry):
    """Get schedules from service-based entry structure."""
    return entry.options.get("services", {}).get("default", {}).get("schedules", {})


async def test_single_schedule_persists(hass: HomeAssistant) -> None:
    """Test that a single schedule is saved correctly."""
    entry = _create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add a schedule
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
            "name": "Test Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify via calendar entity that schedule exists
    from datetime import datetime

    from homeassistant.util import dt as dt_util

    # The entity ID should just be the calendar name
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")
    start = datetime(2024, 5, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 9, 30, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Test Schedule"

    # Verify schedule is in config entry
    schedules = _get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["name"] == "Test Schedule"
    assert schedule["schedule_type"] == "date"


async def test_multiple_schedules_persist(hass: HomeAssistant) -> None:
    """Test that multiple schedules are saved correctly."""
    entry = _create_service_entry()
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
            "name": "Summer Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

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
            "name": "Winter Schedule",
            "start_month": "12",
            "start_day": 1,
            "end_month": "2",
            "end_day": 28,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify both schedules exist
    schedules = _get_schedules_from_entry(entry)
    assert len(schedules) == 2

    schedule_names = {s["name"] for s in schedules.values()}
    assert schedule_names == {"Summer Schedule", "Winter Schedule"}


async def test_schedule_with_configuration_persists(hass: HomeAssistant) -> None:
    """Test that schedule configuration is saved correctly."""
    entry = _create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add schedule with configuration
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
            "name": "Configured Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "summary: Custom Event\ndescription: Test Description",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify configuration is saved
    schedules = _get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert "configuration" in schedule
    assert schedule["configuration"]["summary"] == "Custom Event"
    assert schedule["configuration"]["description"] == "Test Description"


async def test_default_configuration_persists(hass: HomeAssistant) -> None:
    """Test that default configuration is saved correctly."""
    entry = _create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Set default configuration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "default_configuration"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"configuration": "summary: Default Event\nlocation: Home"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify default configuration is saved
    services = entry.options.get("services", {})
    default_service = services.get("default", {})
    config = default_service.get("configuration", {})
    assert config["summary"] == "Default Event"
    assert config["location"] == "Home"


async def test_edit_schedule_preserves_others(hass: HomeAssistant) -> None:
    """Test that editing one schedule doesn't affect others."""
    # Start with two schedules
    schedules = {
        "schedule-1": {
            "name": "Schedule 1",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "schedule-1",
        },
        "schedule-2": {
            "name": "Schedule 2",
            "schedule_type": "date",
            "start_month": 12,
            "start_day": 1,
            "end_month": 2,
            "end_day": 28,
            "uid": "schedule-2",
        },
    }
    entry = _create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Edit first schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_id": "schedule-1"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Modified Schedule 1",  # Changed name
            "start_month": "6",
            "start_day": 1,
            "end_month": "9",  # Changed end month
            "end_day": 30,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify both schedules still exist and second is unchanged
    updated_schedules = _get_schedules_from_entry(entry)
    assert len(updated_schedules) == 2

    # Check modified schedule
    modified_schedule = updated_schedules["schedule-1"]
    assert modified_schedule["name"] == "Modified Schedule 1"
    assert modified_schedule["end_month"] == 9

    # Check unchanged schedule
    unchanged_schedule = updated_schedules["schedule-2"]
    assert unchanged_schedule["name"] == "Schedule 2"
    assert unchanged_schedule["start_month"] == 12
    assert unchanged_schedule["end_month"] == 2


async def test_remove_schedule_preserves_others(hass: HomeAssistant) -> None:
    """Test that removing one schedule doesn't affect others."""
    # Start with two schedules
    schedules = {
        "schedule-1": {
            "name": "Schedule 1",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "schedule-1",
        },
        "schedule-2": {
            "name": "Schedule 2",
            "schedule_type": "date",
            "start_month": 12,
            "start_day": 1,
            "end_month": 2,
            "end_day": 28,
            "uid": "schedule-2",
        },
    }
    entry = _create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Remove first schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "remove_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_id": "schedule-1"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm": True}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify only second schedule remains
    remaining_schedules = _get_schedules_from_entry(entry)
    assert len(remaining_schedules) == 1
    assert "schedule-1" not in remaining_schedules
    assert "schedule-2" in remaining_schedules

    remaining_schedule = remaining_schedules["schedule-2"]
    assert remaining_schedule["name"] == "Schedule 2"
    assert remaining_schedule["start_month"] == 12
