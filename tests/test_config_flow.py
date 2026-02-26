"""Test the Scheduler config flow."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN
from tests.conftest import get_configuration_from_entry, get_schedules_from_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


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


async def test_options_flow_add_date_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test adding a date-based schedule via options flow."""
    entry = create_service_entry()
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
    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["name"] == "Summer Schedule"
    assert schedule["schedule_type"] == "date"
    assert schedule["start_month"] == 6
    assert schedule["start_day"] == 1


async def test_options_flow_add_week_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test adding a week-based schedule via options flow."""
    entry = create_service_entry()
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
            "start_week": "0_partial",
            "start_day_of_week": "0",
            "end_month": "6",
            "end_week": "4",
            "end_day_of_week": "4",
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["name"] == "Week Schedule"
    assert schedule["schedule_type"] == "week"


async def test_options_flow_add_nth_day_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test adding an nth-day schedule via options flow."""
    entry = create_service_entry()
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

    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = list(schedules.values())[0]
    assert schedule["name"] == "Nth Day Schedule"
    assert schedule["schedule_type"] == "nth-day"
    assert schedule["start_offset"] == 2
    assert schedule["end_offset"] == 3


async def test_options_flow_default_configuration(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test setting default configuration."""
    entry = create_service_entry()
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

    config = get_configuration_from_entry(entry)
    assert config == {"key": "value", "other": 123}


async def test_options_flow_invalid_yaml(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test invalid YAML in configuration."""
    entry = create_service_entry()
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
    assert result["errors"]["base"] == "invalid_yaml_with_details"
    assert "details" in result["description_placeholders"]
    assert "Invalid YAML:" in result["description_placeholders"]["details"]


async def test_options_flow_edit_schedule_with_configuration(
    hass: HomeAssistant, create_service_entry
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
    entry = create_service_entry(schedules=schedules)
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


async def test_form_duplicate_scheduler_name(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test that duplicate scheduler names are rejected."""
    entry1 = create_service_entry("My Scheduler")
    entry1.add_to_hass(hass)

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
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test that duplicate scheduler names are rejected (case insensitive)."""
    entry1 = create_service_entry("My Scheduler")
    entry1.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"scheduler_name": "my scheduler"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"scheduler_name": "duplicate_scheduler_name"}


async def test_add_schedule_duplicate_name(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

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
    assert result["errors"] == {"name": "duplicate_name"}


async def test_edit_schedule_keep_same_name(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

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

    assert result["type"] == FlowResultType.CREATE_ENTRY
    services = result["data"]["services"]
    updated_schedule = services["default"]["schedules"]["test-id"]
    assert updated_schedule["name"] == "My Schedule"
    assert updated_schedule["end_month"] == 9


async def test_edit_schedule_remove_configuration(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

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

    assert result["type"] == FlowResultType.CREATE_ENTRY
    services = result["data"]["services"]
    updated_schedule = services["default"]["schedules"]["test-id"]
    assert updated_schedule["name"] == "Test Schedule"
    assert "configuration" not in updated_schedule


async def test_holiday_import_no_holidays_imported(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test no_holidays_imported when all selected holidays are skipped."""
    # Full-year blocking schedule so every holiday import will overlap
    schedules = {
        "blocker": {
            "uid": "blocker",
            "name": "Blocker",
            "schedule_type": "date",
            "start_month": 1,
            "start_day": 1,
            "end_month": 12,
            "end_day": 31,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # 5 mock holidays, each overlapping with the full-year blocker
    mock_holidays = {
        f"Holiday {i}": {
            "pattern": {
                "schedule_type": "date",
                "start_month": i,
                "start_day": 1,
                "end_month": i,
                "end_day": 28,
                "description": f"Month {i} holiday",
            },
            "dates": [date(2026, i, 1)],
        }
        for i in range(1, 6)  # 5 holidays
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"US": "United States"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=mock_holidays),
        ),
    ):
        # Menu → import_holidays (shows country form)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "import_holidays"}
        )
        assert result["step_id"] == "import_holidays"

        # Submit country → shows categories form
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"country": "US"}
        )
        assert result["step_id"] == "import_holidays_categories"

        # Submit categories → shows holiday selector
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"categories": ["public"]}
        )
        assert result["step_id"] == "import_holidays_select"

        # Submit all 5 holidays with skip_on_overlap=True
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "holidays": list(mock_holidays.keys()),
                "skip_on_overlap": True,
                "overwrite_existing": False,
                "include_country_name": False,
            },
        )

    # All 5 overlap → shows no_holidays_imported key (details logged, not shown to user)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_holidays_imported"


async def test_form_empty_scheduler_name(hass: HomeAssistant) -> None:
    """Test that an empty scheduler name is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"scheduler_name": "   "},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"scheduler_name": "empty_scheduler_name"}


async def test_add_schedule_duplicate_name_case_insensitive(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test that duplicate schedule names are rejected (case insensitive)."""
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
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

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
            "name": "summer schedule",
            "start_month": "9",
            "start_day": 1,
            "end_month": "11",
            "end_day": 30,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"name": "duplicate_name"}


async def test_remove_schedule_no_schedules(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test remove schedule aborts when no schedules exist."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_schedule"},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_schedules"


async def test_remove_schedule_not_confirmed(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test remove schedule aborts when confirmation is not provided."""
    schedules = {
        "test-id": {
            "uid": "test-id",
            "name": "Test Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "test-id"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"confirm": False},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_confirmed"


async def test_remove_schedule_legacy_entry(hass: HomeAssistant) -> None:
    """Test removing a schedule from a legacy options structure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={"scheduler_name": "Test Scheduler"},
        options={
            "schedules": {
                "legacy-id": {
                    "uid": "legacy-id",
                    "name": "Legacy Schedule",
                    "schedule_type": "date",
                    "start_month": 1,
                    "start_day": 1,
                    "end_month": 12,
                    "end_day": 31,
                }
            }
        },
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "legacy-id"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"confirm": True},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["services"]["default"]["schedules"] == {}


async def test_edit_week_schedule_removes_days(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test editing a week schedule removes optional day fields."""
    schedules = {
        "week-id": {
            "uid": "week-id",
            "name": "Week Schedule",
            "schedule_type": "week",
            "start_month": 1,
            "start_week": 0,
            "start_week_type": "full",
            "start_day_of_week": 1,
            "end_month": 2,
            "end_week": 0,
            "end_week_type": "partial",
            "end_day_of_week": 5,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "edit_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "week-id"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Week Schedule",
            "start_month": "1",
            "start_week": "0_full",
            "start_day_of_week": "",
            "end_month": "3",
            "end_week": "0_partial",
            "end_day_of_week": "",
            "configuration": "",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    updated = result["data"]["services"]["default"]["schedules"]["week-id"]
    assert updated["start_week_type"] == "full"
    assert updated["end_week_type"] == "partial"
    assert "start_day_of_week" not in updated
    assert "end_day_of_week" not in updated


async def test_edit_nth_day_schedule(hass: HomeAssistant, create_service_entry) -> None:
    """Test editing an nth-day schedule updates fields."""
    schedules = {
        "nth-id": {
            "uid": "nth-id",
            "name": "Nth Day Schedule",
            "schedule_type": "nth-day",
            "month": 3,
            "occurrence": 1,
            "day_of_week": 1,
            "start_offset": 2,
            "end_offset": 3,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "edit_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "nth-id"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Nth Day Schedule",
            "month": "4",
            "occurrence": "2",
            "day_of_week": "2",
            "start_offset": 0,
            "end_offset": 1,
            "configuration": "",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    updated = result["data"]["services"]["default"]["schedules"]["nth-id"]
    assert updated["month"] == 4
    assert updated["occurrence"] == 2
    assert updated["day_of_week"] == 2
    assert updated["start_offset"] == 0
    assert updated["end_offset"] == 1


async def test_default_configuration_invalid_yaml(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test invalid YAML in default configuration."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "default_configuration"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"configuration": "invalid: yaml: ["},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_yaml_with_details"
    assert "details" in result["description_placeholders"]


async def test_default_configuration_entry_not_found(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test default configuration handles missing config entry."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "default_configuration"},
    )

    with patch.object(hass.config_entries, "async_get_entry", return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"configuration": "key: value"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "entry_not_found"


async def test_import_holidays_skip_overlap_false_imports(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test importing holidays when overlaps are allowed."""
    schedules = {
        "blocker": {
            "uid": "blocker",
            "name": "Blocker",
            "schedule_type": "date",
            "start_month": 1,
            "start_day": 1,
            "end_month": 12,
            "end_day": 31,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Holiday A": {
            "pattern": {
                "schedule_type": "date",
                "start_month": 1,
                "start_day": 1,
                "end_month": 1,
                "end_day": 1,
                "description": "Holiday A",
            },
            "dates": [date(2026, 1, 1)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"US": "United States"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=mock_holidays),
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "import_holidays"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"country": "US"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"categories": ["public"]}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "holidays": ["Holiday A"],
                "skip_on_overlap": False,
                "overwrite_existing": False,
                "include_country_name": False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = result["data"]["services"]["default"]["schedules"]
    assert len(schedules) == 2
    assert any(schedule["name"] == "Holiday A" for schedule in schedules.values())


async def test_import_holidays_overwrite_existing(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test importing holidays overwrites existing schedules."""
    schedules = {
        "existing-id": {
            "uid": "existing-id",
            "name": "Holiday A",
            "schedule_type": "date",
            "start_month": 5,
            "start_day": 1,
            "end_month": 5,
            "end_day": 2,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Holiday A": {
            "pattern": {
                "schedule_type": "date",
                "start_month": 7,
                "start_day": 4,
                "end_month": 7,
                "end_day": 4,
                "description": "Holiday A",
            },
            "dates": [date(2026, 7, 4)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"US": "United States"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=mock_holidays),
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "import_holidays"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"country": "US"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"categories": ["public"]}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "holidays": ["Holiday A"],
                "skip_on_overlap": True,
                "overwrite_existing": True,
                "include_country_name": False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = result["data"]["services"]["default"]["schedules"]
    assert list(schedules.keys()) == ["existing-id"]
    assert schedules["existing-id"]["start_month"] == 7


async def test_import_holidays_include_country_name(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test importing holidays with country name appended."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Holiday A": {
            "pattern": {
                "schedule_type": "date",
                "start_month": 12,
                "start_day": 25,
                "end_month": 12,
                "end_day": 25,
                "description": "Holiday A",
            },
            "dates": [date(2026, 12, 25)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"US": "United States"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=mock_holidays),
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "import_holidays"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"country": "US"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"categories": ["public"]}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "holidays": ["Holiday A"],
                "skip_on_overlap": True,
                "overwrite_existing": False,
                "include_country_name": True,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = result["data"]["services"]["default"]["schedules"]
    assert any(schedule["name"] == "Holiday A (US)" for schedule in schedules.values())


async def test_import_holidays_no_countries_available(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test import holidays aborts when no countries are available."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
        new=AsyncMock(return_value={}),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "import_holidays"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_countries_available"


async def test_import_holidays_import_error(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test import holidays aborts on unexpected errors."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
        new=AsyncMock(side_effect=Exception("boom")),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "import_holidays"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "import_error"


async def test_import_holidays_no_holidays_selected(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test import holidays requires at least one holiday selection."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Holiday A": {
            "pattern": {
                "schedule_type": "date",
                "start_month": 1,
                "start_day": 1,
                "end_month": 1,
                "end_day": 1,
                "description": "Holiday A",
            },
            "dates": [date(2026, 1, 1)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"US": "United States"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=mock_holidays),
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "import_holidays"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"country": "US"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"categories": ["public"]}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "holidays": [],
                "skip_on_overlap": True,
                "overwrite_existing": False,
                "include_country_name": False,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"holidays": "no_holidays_selected"}
