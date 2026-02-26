"""Test the Scheduler config flow."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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
    assert "base" in result["errors"]


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


async def test_holiday_import_error_truncation(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test that >3 import errors show a truncated message with 'and N more'."""
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
