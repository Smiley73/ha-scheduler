"""Test the Scheduler config flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

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

    await hass.config_entries.options.async_configure(
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


async def test_options_add_schedule_invalid_month_range(
    hass: HomeAssistant, empty_hub_entry
):
    """Test adding schedule with wrap-around month range (Dec-Jan) is now allowed."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
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

    # Wrap-around schedules are now supported (e.g., winter schedules Nov-Feb)
    assert result4["type"] == FlowResultType.CREATE_ENTRY

    # Verify the schedule was created
    schedules = empty_hub_entry.data.get("schedules", {})
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["start_month"] == 12
    assert schedule["end_month"] == 1


async def test_options_add_schedule_invalid_day_range(
    hass: HomeAssistant, empty_hub_entry
):
    """Test adding schedule with invalid day range."""
    empty_hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
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

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
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

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
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


async def test_options_add_schedule_date_overlap(hass: HomeAssistant):
    """Test adding a date schedule that overlaps with existing schedule."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create hub with existing schedule (Jan 1 - Jun 30)
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "existing_schedule": {
                    "name": "Existing Schedule",
                    "start_month": 1,
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 30,
                },
            },
        },
        entry_id="test_overlap_hub",
    )

    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Overlapping Schedule",
            "schedule_type": "date",
        },
    )

    # Try to add schedule that overlaps (May 1 - Aug 31)
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "5",
            "end_month": "8",
            "start_day": 1,
            "end_day": 31,
        },
    )

    assert result4["type"] == FlowResultType.FORM
    assert (
        result4["errors"]["base"]
        == "Schedule overlaps with existing schedule 'Existing Schedule'"
    )


async def test_options_add_schedule_week_overlap(hass: HomeAssistant):
    """Test adding a week schedule that overlaps with existing schedule."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create hub with existing week schedule
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "existing_week": {
                    "name": "Existing Week Schedule",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "week",
                    "start_day_of_week": 0,
                    "end_day_of_week": 4,
                    "start_week": 0,
                    "end_week": 2,
                },
            },
        },
        entry_id="test_week_overlap_hub",
    )

    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Overlapping Week Schedule",
            "schedule_type": "week",
        },
    )

    # Try to add schedule that overlaps
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "6",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 1,
            "end_week": 3,
        },
    )

    assert result4["type"] == FlowResultType.FORM
    assert (
        result4["errors"]["base"]
        == "Schedule overlaps with existing schedule 'Existing Week Schedule'"
    )


async def test_options_add_schedule_overlap_different_type(hass: HomeAssistant):
    """Test adding a schedule with different type checks overlap."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create hub with date-based schedule covering full year
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "date_schedule": {
                    "name": "Date Schedule",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
            },
        },
        entry_id="test_diff_type_hub",
    )

    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Week Schedule",
            "schedule_type": "week",
        },
    )

    # Add week schedule that overlaps with date schedule
    result4 = await hass.config_entries.options.async_configure(
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

    # Should detect overlap even though types are different
    assert result4["type"] == FlowResultType.FORM
    assert (
        result4["errors"]["base"]
        == "Schedule overlaps with existing schedule 'Date Schedule'"
    )


async def test_options_add_schedule_no_overlap_different_type(hass: HomeAssistant):
    """Test adding a schedule with different type that doesn't overlap."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create hub with date-based schedule for first half of year
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "date_schedule": {
                    "name": "Date Schedule",
                    "start_month": 1,
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 30,
                },
            },
        },
        entry_id="test_diff_type_no_overlap_hub",
    )

    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Week Schedule",
            "schedule_type": "week",
        },
    )

    # Add week schedule for second half of year (no overlap)
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "7",
            "end_month": "12",
            "start_day_of_week": "0",
            "end_day_of_week": "6",
            "start_week": 0,
            "end_week": 4,
        },
    )

    # Should succeed as there's no overlap
    assert result4["type"] == FlowResultType.CREATE_ENTRY


async def test_options_edit_schedule_no_self_overlap(hass: HomeAssistant):
    """Test editing a schedule doesn't check overlap with itself."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

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
                    "end_day": 30,
                },
            },
        },
        entry_id="test_edit_hub",
    )

    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "edit_schedule"},
    )

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "schedule_1"},
    )

    # Edit the schedule (should not check overlap with itself)
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "1",
            "end_month": "7",  # Extended range
            "start_day": 1,
            "end_day": 15,
        },
    )

    assert result4["type"] == FlowResultType.CREATE_ENTRY


async def test_options_add_schedule_no_overlap(hass: HomeAssistant):
    """Test adding a schedule that doesn't overlap."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create hub with existing schedule (Jan 1 - Jun 30)
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "first_half": {
                    "name": "First Half",
                    "start_month": 1,
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 30,
                },
            },
        },
        entry_id="test_no_overlap_hub",
    )

    hub_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_schedule"},
    )

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Second Half",
            "schedule_type": "date",
        },
    )

    # Add schedule that doesn't overlap (Jul 1 - Dec 31)
    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "start_month": "7",
            "end_month": "12",
            "start_day": 1,
            "end_day": 31,
        },
    )

    assert result4["type"] == FlowResultType.CREATE_ENTRY


async def test_options_add_schedule_name_none_rejected(hass: HomeAssistant, hub_entry):
    """Test that schedule name 'None' is rejected."""
    hub_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hub_entry.entry_id)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    assert result["type"] == "menu"

    # Select add_schedule
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )

    # Try to add a schedule with name "None"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "None",
            "schedule_type": "date",
        },
    )

    # Should show error
    assert result["type"] == "form"
    assert result["errors"] == {"name": "invalid_name"}

    # Try with "none" (lowercase)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "none",
            "schedule_type": "date",
        },
    )

    # Should show error
    assert result["type"] == "form"
    assert result["errors"] == {"name": "invalid_name"}

    # Try with "NONE" (uppercase)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "NONE",
            "schedule_type": "date",
        },
    )

    # Should show error
    assert result["type"] == "form"
    assert result["errors"] == {"name": "invalid_name"}


async def test_options_rename_schedule(hass: HomeAssistant, hub_entry):
    """Test renaming a schedule."""
    hub_entry.add_to_hass(hass)

    # Start options flow
    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select rename_schedule
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "rename_schedule"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rename_schedule"

    # Select the schedule to rename
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_id": "test_schedule_1"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rename_schedule"

    # Enter new name
    with patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"name": "Renamed Schedule"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify the schedule was renamed
    entry = hass.config_entries.async_get_entry(hub_entry.entry_id)
    assert entry.data["schedules"]["test_schedule_1"]["name"] == "Renamed Schedule"


async def test_options_rename_no_schedules(hass: HomeAssistant, empty_hub_entry):
    """Test rename aborts when no schedules exist."""
    empty_hub_entry.add_to_hass(hass)

    # Start options flow
    result = await hass.config_entries.options.async_init(empty_hub_entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select rename_schedule
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "rename_schedule"}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_schedules"


async def test_options_rename_schedule_invalid_name(hass: HomeAssistant, hub_entry):
    """Test renaming a schedule with invalid name 'None'."""
    hub_entry.add_to_hass(hass)

    # Start options flow
    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Select rename_schedule
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "rename_schedule"}
    )

    # Select the schedule to rename
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_id": "test_schedule_1"}
    )

    # Try to rename with "None"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "None"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rename_schedule"
    assert result["errors"] == {"name": "invalid_name"}


async def test_options_add_schedule_invalid_week_range(hass: HomeAssistant, hub_entry):
    """Test adding a schedule with invalid week range."""
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    assert result["type"] == "menu"

    # Start add schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_schedule"}
    )

    # Enter schedule name and type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": "Invalid Week Schedule", "schedule_type": "week"},
    )

    # Try to configure with start_week > end_week
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "1",
            "start_week": 3,
            "start_day_of_week": "0",
            "end_month": "12",
            "end_week": 1,  # Less than start_week
            "end_day_of_week": "6",
        },
    )

    assert result["type"] == "form"
    assert "base" in result["errors"]


async def test_options_add_schedule_scalar_yaml(hass: HomeAssistant, hub_entry):
    """Test adding a schedule with scalar YAML value (should fail)."""
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Start add schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_schedule"}
    )

    # Enter schedule name and type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": "Scalar YAML Schedule", "schedule_type": "date"},
    )

    # Try to configure with scalar YAML (should fail)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "1",
            "start_day": 1,
            "end_month": "12",
            "end_day": 31,
            "additional_yaml": "just_a_string",  # Scalar value, not dict/list
        },
    )

    assert result["type"] == "form"
    assert "base" in result["errors"]


async def test_options_add_schedule_month_validation(hass: HomeAssistant):
    """Test month validation in schedule configuration with string conversion."""
    # Create a hub with no schedules to avoid overlap
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_month_validation_hub",
    )

    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Start add schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_schedule"}
    )

    # Enter schedule name and type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": "Month Validation Schedule", "schedule_type": "date"},
    )

    # The form should accept month values as strings (from selector)
    # This tests the string-to-int conversion path
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "6",  # String value from selector
            "start_day": 1,
            "end_month": "8",  # String value from selector
            "end_day": 31,
            "additional_yaml": "",
        },
    )

    # Should succeed
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_add_schedule_week_day_validation(hass: HomeAssistant):
    """Test day of week validation in week-based schedule with string conversion."""
    # Create a hub with no schedules to avoid overlap
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_week_validation_hub",
    )

    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Start add schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_schedule"}
    )

    # Enter schedule name and type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": "Week Day Schedule", "schedule_type": "week"},
    )

    # Configure with string day_of_week values (from selector)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "1",
            "start_week": 0,
            "start_day_of_week": "0",  # String value from selector
            "end_month": "12",
            "end_week": 4,
            "end_day_of_week": "6",  # String value from selector
            "additional_yaml": "",
        },
    )

    # Should succeed
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_edit_schedule_with_overlap_check(hass: HomeAssistant):
    """Test editing a schedule doesn't trigger self-overlap."""
    # Create hub with two schedules
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
                    "end_day": 30,
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
        entry_id="test_edit_overlap_hub",
    )

    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Start edit schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "edit_schedule"}
    )

    # Select schedule 1 to edit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"schedule_id": "schedule_1"}
    )

    # Edit schedule 1 with same dates (should not trigger self-overlap)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "1",
            "start_day": 1,
            "end_month": "6",
            "end_day": 30,
            "additional_yaml": "",
        },
    )

    # Should succeed without overlap error
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_add_schedule_cross_type_overlap(hass: HomeAssistant):
    """Test overlap detection between date and week schedules."""
    # Create hub with a date-based schedule
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "date_schedule": {
                    "name": "Date Schedule",
                    "start_month": 6,
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 30,
                },
            },
        },
        entry_id="test_cross_overlap_hub",
    )

    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Start add schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_schedule"}
    )

    # Enter schedule name and type (week-based)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": "Week Schedule", "schedule_type": "week"},
    )

    # Try to add week schedule that overlaps with date schedule (June)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "6",
            "start_week": 0,
            "start_day_of_week": "0",
            "end_month": "6",
            "end_week": 4,
            "end_day_of_week": "6",
            "additional_yaml": "",
        },
    )

    # Should detect overlap
    assert result["type"] == FlowResultType.FORM
    assert "base" in result["errors"]


async def test_options_add_schedule_invalid_day_of_week_type(hass: HomeAssistant):
    """Test validation when day_of_week is not an integer."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_dow_type_hub",
    )

    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Start add schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_schedule"}
    )

    # Enter schedule name and type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": "DOW Type Schedule", "schedule_type": "week"},
    )

    # This should succeed with string values that get converted
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "6",
            "start_week": 0,
            "start_day_of_week": "0",
            "end_month": "8",
            "end_week": 2,
            "end_day_of_week": "4",
            "additional_yaml": "",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_add_schedule_week_number_validation(hass: HomeAssistant):
    """Test week number validation with float conversion."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_week_num_hub",
    )

    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Start add schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_schedule"}
    )

    # Enter schedule name and type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": "Week Number Schedule", "schedule_type": "week"},
    )

    # Configure with float week values (should be converted to int)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "1",
            "start_week": 0.0,  # Float value
            "start_day_of_week": "0",
            "end_month": "12",
            "end_week": 4.0,  # Float value
            "end_day_of_week": "6",
            "additional_yaml": "",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_add_schedule_day_float_conversion(hass: HomeAssistant):
    """Test day value float to int conversion."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_day_float_hub",
    )

    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)

    # Start add schedule flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_schedule"}
    )

    # Enter schedule name and type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": "Day Float Schedule", "schedule_type": "date"},
    )

    # Configure with float day values (from NumberSelector)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "start_month": "6",
            "start_day": 1.0,  # Float value
            "end_month": "8",
            "end_day": 31.0,  # Float value
            "additional_yaml": "",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_translation_fallback_paths(hass: HomeAssistant):
    """Test translation fallback when translations are not available."""
    from custom_components.scheduler.config_flow import (
        _get_day_of_week_options,
        _get_month_options,
        _get_schedule_type_options,
    )

    # Test with no translations loaded
    hass.data["translations"] = {}

    # Should return options with default English labels
    schedule_options = _get_schedule_type_options(hass)
    assert len(schedule_options) == 2
    assert schedule_options[0]["value"] == "date"
    assert schedule_options[1]["value"] == "week"

    month_options = _get_month_options(hass)
    assert len(month_options) == 12
    assert month_options[0]["value"] == "1"
    assert month_options[11]["value"] == "12"

    dow_options = _get_day_of_week_options(hass)
    assert len(dow_options) == 7
    assert dow_options[0]["value"] == "0"
    assert dow_options[6]["value"] == "6"


async def test_check_overlap_functions():
    """Test overlap checking functions directly."""
    from custom_components.scheduler.config_flow import (
        check_date_overlap,
        check_date_week_overlap,
        check_week_overlap,
    )

    # Test date overlap - no overlap
    assert not check_date_overlap(1, 1, 6, 30, 7, 1, 12, 31)

    # Test date overlap - with overlap
    assert check_date_overlap(1, 1, 6, 30, 5, 1, 8, 31)

    # Test date overlap - wrap around both
    assert check_date_overlap(11, 1, 2, 28, 12, 1, 1, 31)

    # Test week overlap - no overlap
    assert not check_week_overlap(1, 0, 0, 6, 0, 6, 7, 0, 0, 12, 0, 6)

    # Test week overlap - with overlap
    assert check_week_overlap(1, 0, 0, 12, 4, 6, 6, 0, 0, 8, 2, 4)

    # Test date-week overlap
    assert check_date_week_overlap(6, 1, 6, 30, 6, 0, 0, 6, 4, 6)


async def test_handle_validation_error_function():
    """Test the handle_validation_error function."""
    from custom_components.scheduler.config_flow import handle_validation_error

    # Test overlap error
    error_key, placeholders = handle_validation_error(
        ValueError("Schedule overlaps with existing schedule 'Test'")
    )
    assert error_key == "schedule_overlap"

    # Test YAML error
    error_key, placeholders = handle_validation_error(ValueError("Invalid YAML"))
    assert error_key == "invalid_yaml"

    # Test month error
    error_key, placeholders = handle_validation_error(
        ValueError("Start month must be between 1 and 12")
    )
    assert error_key == "invalid_month_range"

    # Test day of week error
    error_key, placeholders = handle_validation_error(
        ValueError("Day of week must be between 0 and 6")
    )
    assert error_key == "invalid_day_of_week"

    # Test week error
    error_key, placeholders = handle_validation_error(
        ValueError("Start week must be before end week")
    )
    assert error_key == "invalid_week_range"

    # Test day error
    error_key, placeholders = handle_validation_error(
        ValueError("Start day must be between 1 and 31")
    )
    assert error_key == "invalid_day_range"

    # Test generic error
    error_key, placeholders = handle_validation_error(ValueError("Unknown error"))
    assert error_key == "invalid_input"


async def test_validate_schedule_input_missing_fields():
    """Test validation with missing required fields."""
    from custom_components.scheduler.config_flow import validate_schedule_input

    # Test missing start_day for date schedule
    with pytest.raises(ValueError, match="Start day must be provided"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "date",
                "start_month": 1,
                "end_month": 12,
                "end_day": 31,
            },
        )

    # Test missing end_day for date schedule
    with pytest.raises(ValueError, match="End day must be provided"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "date",
                "start_month": 1,
                "start_day": 1,
                "end_month": 12,
            },
        )

    # Test missing start_day_of_week for week schedule
    with pytest.raises(ValueError, match="Start day of week must be provided"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "week",
                "start_month": 1,
                "end_month": 12,
                "start_week": 0,
                "end_week": 4,
                "end_day_of_week": 6,
            },
        )

    # Test missing end_day_of_week for week schedule
    with pytest.raises(ValueError, match="End day of week must be provided"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "week",
                "start_month": 1,
                "end_month": 12,
                "start_week": 0,
                "end_week": 4,
                "start_day_of_week": 0,
            },
        )

    # Test missing start_week for week schedule
    with pytest.raises(ValueError, match="Start week must be provided"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "week",
                "start_month": 1,
                "end_month": 12,
                "start_day_of_week": 0,
                "end_day_of_week": 6,
                "end_week": 4,
            },
        )

    # Test missing end_week for week schedule
    with pytest.raises(ValueError, match="End week must be provided"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "week",
                "start_month": 1,
                "end_month": 12,
                "start_week": 0,
                "start_day_of_week": 0,
                "end_day_of_week": 6,
            },
        )


async def test_validate_schedule_input_type_errors():
    """Test validation with wrong types."""
    from custom_components.scheduler.config_flow import validate_schedule_input

    # Test non-integer month values (after string conversion fails)
    with pytest.raises(ValueError, match="Months must be integers"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "date",
                "start_month": None,  # Will fail type check
                "start_day": 1,
                "end_month": 12,
                "end_day": 31,
            },
        )


async def test_validate_schedule_input_range_errors():
    """Test validation with out of range values."""
    from custom_components.scheduler.config_flow import validate_schedule_input

    # Test day out of range
    with pytest.raises(ValueError, match="Start day must be between 1 and 31"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "date",
                "start_month": 1,
                "start_day": 0,
                "end_month": 12,
                "end_day": 31,
            },
        )

    with pytest.raises(ValueError, match="End day must be between 1 and 31"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "date",
                "start_month": 1,
                "start_day": 1,
                "end_month": 12,
                "end_day": 32,
            },
        )

    # Test day_of_week out of range
    with pytest.raises(ValueError, match="Start day of week must be between 0 and 6"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "week",
                "start_month": 1,
                "start_week": 0,
                "start_day_of_week": 7,
                "end_month": 12,
                "end_week": 4,
                "end_day_of_week": 6,
            },
        )

    with pytest.raises(ValueError, match="End day of week must be between 0 and 6"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "week",
                "start_month": 1,
                "start_week": 0,
                "start_day_of_week": 0,
                "end_month": 12,
                "end_week": 4,
                "end_day_of_week": 7,
            },
        )

    # Test week out of range
    with pytest.raises(ValueError, match="Start week must be between 0 and 4"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "week",
                "start_month": 1,
                "start_week": 5,
                "start_day_of_week": 0,
                "end_month": 12,
                "end_week": 4,
                "end_day_of_week": 6,
            },
        )

    with pytest.raises(ValueError, match="End week must be between 0 and 4"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "week",
                "start_month": 1,
                "start_week": 0,
                "start_day_of_week": 0,
                "end_month": 12,
                "end_week": 5,
                "end_day_of_week": 6,
            },
        )

    # Test month out of range
    with pytest.raises(ValueError, match="Start month must be between 1 and 12"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "date",
                "start_month": 0,
                "start_day": 1,
                "end_month": 12,
                "end_day": 31,
            },
        )

    with pytest.raises(ValueError, match="End month must be between 1 and 12"):
        await validate_schedule_input(
            None,
            {
                "name": "Test",
                "schedule_type": "date",
                "start_month": 1,
                "start_day": 1,
                "end_month": 13,
                "end_day": 31,
            },
        )


async def test_config_flow_description_placeholders(hass: HomeAssistant):
    """Test that config flow shows description placeholders."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that description placeholders are present
    assert result["type"] == FlowResultType.FORM
    assert "description_placeholders" in result
    assert "info" in result["description_placeholders"]
