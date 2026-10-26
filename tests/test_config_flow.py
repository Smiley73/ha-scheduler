"""Test the Scheduler config flow."""

from contextlib import ExitStack, asynccontextmanager
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from custom_components.ha_scheduler.const import DOMAIN
from tests.conftest import get_configuration_from_entry, get_schedules_from_entry
from tests.test_config_flow_edge_cases import _holiday_import_patches

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_HOLIDAY_A_JULY_4 = {
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

_EXISTING_HOLIDAY_A = {
    "uid": "existing-id",
    "name": "Holiday A",
    "schedule_type": "date",
    "start_month": 5,
    "start_day": 1,
    "end_month": 5,
    "end_day": 2,
}

_SUMMER_BLOCKER = {
    "uid": "blocker-id",
    "name": "Summer Blocker",
    "schedule_type": "date",
    "start_month": 7,
    "start_day": 1,
    "end_month": 7,
    "end_day": 31,
}


@asynccontextmanager
async def _import_holidays_select(
    hass: HomeAssistant, entry, holidays: dict, categories=("public",)
):
    """Walk the options flow to the holiday selection form with fixed lookups.

    Yields the ``import_holidays_select`` form result; the holiday_importer
    lookups stay patched until the block exits.
    """
    with ExitStack() as stack:
        for holiday_patch in _holiday_import_patches(holidays, categories):
            stack.enter_context(holiday_patch)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        for user_input in (
            {"next_step_id": "import_holidays"},
            {"country": "US"},
            {"categories": list(categories)},
        ):
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], user_input
            )
        assert result["step_id"] == "import_holidays_select"
        yield result


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
    schedule = next(iter(schedules.values()))
    assert schedule["name"] == "Summer Schedule"
    assert schedule["schedule_type"] == "date"
    assert schedule["start_month"] == 6
    assert schedule["start_day"] == 1
    assert schedule["end_month"] == 8
    assert schedule["end_day"] == 31
    assert schedule["uid"] == next(iter(schedules))

    # The calendar entity serves the new schedule
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")
    start = datetime(2024, 5, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 9, 30, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)
    assert [event.summary for event in events] == ["Summer Schedule"]


async def test_options_flow_add_multiple_schedules(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test a second schedule is stored alongside the first."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for name, start_month, end_month in (
        ("Summer Schedule", "6", "8"),
        ("Winter Schedule", "12", "2"),
    ):
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
                "name": name,
                "start_month": start_month,
                "start_day": 1,
                "end_month": end_month,
                "end_day": 28,
                "configuration": "",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 2
    assert {s["name"] for s in schedules.values()} == {
        "Summer Schedule",
        "Winter Schedule",
    }


async def test_options_flow_rejects_invalid_week_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test rejecting week schedules that create reversed date ranges."""
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
            "name": "Invalid Week Schedule",
            "start_month": "3",
            "start_week": "1",
            "start_day_of_week": "6",
            "end_month": "3",
            "end_week": "1",
            "end_day_of_week": "4",
            "configuration": "",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_week_schedule"


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
    schedule = next(iter(schedules.values()))
    assert schedule["name"] == "Nth Day Schedule"
    assert schedule["schedule_type"] == "nth-day"
    assert schedule["start_offset"] == 2
    assert schedule["end_offset"] == 3


async def test_add_nth_day_schedule_first_occurrence(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test adding an nth-day schedule with the "First" occurrence.

    Regression test: the nth-day flow used to reuse the week occurrence
    selector whose first-week values are "0_partial"/"0_full", which crashed
    int() and surfaced a misleading invalid_yaml error.
    """
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "nth-day"}
    )
    assert result["step_id"] == "configure_nth_day"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "First Monday of March",
            "month": "3",
            "occurrence": "0",
            "day_of_week": "0",
            "start_offset": 0,
            "end_offset": 0,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = next(iter(schedules.values()))
    assert schedule["occurrence"] == 0
    assert schedule["day_of_week"] == 0
    assert schedule["month"] == 3


async def test_add_schedule_future_cycle_overlap_error(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test that long-horizon recurring overlaps are rejected.

    Jan 8 does not overlap the second Monday of January in the next 3 years,
    but it does later in the Gregorian cycle and must still be rejected.
    """
    entry = create_service_entry(
        schedules={
            "second-monday": {
                "uid": "second-monday",
                "name": "Second Monday of January",
                "schedule_type": "nth-day",
                "month": 1,
                "occurrence": 1,
                "day_of_week": 0,
                "start_offset": 0,
                "end_offset": 0,
            }
        }
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

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
            "name": "January 8",
            "start_month": "1",
            "start_day": 8,
            "end_month": "1",
            "end_day": 8,
            "configuration": "",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "schedule_overlap_with_name"
    assert result["description_placeholders"]["conflicting_schedule"] == (
        "Second Monday of January"
    )
    assert list(get_schedules_from_entry(entry)) == ["second-monday"]


async def test_options_flow_add_holiday_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test adding a holiday-backed schedule via options flow."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Good Friday": {
            "pattern": {"description": "Movable holiday"},
            "dates": [date(2026, 4, 3)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"DE": "Germany"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=mock_holidays),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.async_prime_holiday_cache",
            new=AsyncMock(),
        ) as mock_prime_holiday_cache,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"next_step_id": "add_schedule"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"schedule_type": "holiday"},
        )
        assert result["step_id"] == "configure_holiday_country"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"country_code": "DE"},
        )
        assert result["step_id"] == "configure_holiday_category"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"category": "public"},
        )
        assert result["step_id"] == "configure_holiday"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Good Friday",
                "holiday_name": "Good Friday",
                "start_offset": 1,
                "end_offset": 2,
                "configuration": "",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    mock_prime_holiday_cache.assert_awaited_once()

    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = next(iter(schedules.values()))
    assert schedule["name"] == "Good Friday"
    assert schedule["schedule_type"] == "holiday"
    assert schedule["country_code"] == "DE"
    assert schedule["category"] == "public"
    assert schedule["holiday_name"] == "Good Friday"
    assert schedule["name_lookup"] == "iexact"
    assert schedule["start_offset"] == 1
    assert schedule["end_offset"] == 2


async def test_options_flow_edit_holiday_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test editing a holiday-backed schedule via options flow."""
    schedules = {
        "holiday-id": {
            "uid": "holiday-id",
            "name": "Good Friday",
            "schedule_type": "holiday",
            "country_code": "DE",
            "category": "public",
            "holiday_name": "Good Friday",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Good Friday": {
            "pattern": {"description": "Movable holiday"},
            "dates": [date(2026, 4, 3)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"DE": "Germany"}),
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
            result["flow_id"],
            {"next_step_id": "edit_schedule"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"schedule_id": "holiday-id"},
        )
        assert result["step_id"] == "configure_holiday_country"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"country_code": "DE"},
        )
        assert result["step_id"] == "configure_holiday_category"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"category": "public"},
        )
        assert result["step_id"] == "configure_holiday"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Good Friday Weekend",
                "holiday_name": "Good Friday",
                "start_offset": 1,
                "end_offset": 1,
                "configuration": "",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    services = result["data"]["services"]
    updated_schedule = services["default"]["schedules"]["holiday-id"]
    assert updated_schedule["name"] == "Good Friday Weekend"
    assert updated_schedule["start_offset"] == 1
    assert updated_schedule["end_offset"] == 1


async def test_options_flow_holiday_schedule_invalid_selection(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test stale holiday selections are rejected when saving."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Good Friday": {
            "pattern": {"description": "Movable holiday"},
            "dates": [date(2026, 4, 3)],
        }
    }
    updated_holidays = {
        "Ostermontag": {
            "pattern": {"description": "Movable holiday"},
            "dates": [date(2026, 4, 6)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"DE": "Germany"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(side_effect=[mock_holidays, updated_holidays]),
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"next_step_id": "add_schedule"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"schedule_type": "holiday"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"country_code": "DE"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"category": "public"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Good Friday",
                "holiday_name": "Good Friday",
                "start_offset": 0,
                "end_offset": 0,
                "configuration": "",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_holiday"
    assert result["errors"] == {"holiday_name": "invalid_holiday_selection"}


async def test_options_flow_holiday_schedule_duplicate_name(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test holiday schedules still enforce duplicate-name validation."""
    schedules = {
        "existing-id": {
            "uid": "existing-id",
            "name": "Good Friday",
            "schedule_type": "date",
            "start_month": 4,
            "start_day": 3,
            "end_month": 4,
            "end_day": 3,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Good Friday": {
            "pattern": {"description": "Movable holiday"},
            "dates": [date(2026, 4, 3)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"DE": "Germany"}),
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
            result["flow_id"],
            {"next_step_id": "add_schedule"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"schedule_type": "holiday"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"country_code": "DE"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"category": "public"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Good Friday",
                "holiday_name": "Good Friday",
                "start_offset": 0,
                "end_offset": 0,
                "configuration": "",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_holiday"
    assert result["errors"] == {"name": "duplicate_name"}


async def test_options_flow_holiday_schedule_future_overlap(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test holiday schedules honor the extended overlap horizon."""
    schedules = {
        "existing-id": {
            "uid": "existing-id",
            "name": "Future Conflict",
            "schedule_type": "date",
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    current_year = date.today().year
    overlap_year = current_year + 9
    mock_holidays = {
        "Good Friday": {
            "pattern": {"description": "Movable holiday"},
            "dates": [date(2026, 4, 3)],
        }
    }

    def _mock_generate_dates(schedule: dict[str, str], year: int):
        if (
            schedule.get("name") in {"Good Friday", "Future Conflict"}
            and year == overlap_year
        ):
            return [(date(year, 4, 1), date(year, 4, 1))]
        return []

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"DE": "Germany"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=mock_holidays),
        ),
        patch(
            "custom_components.ha_scheduler.schedule_generator.generate_schedule_dates",
            side_effect=_mock_generate_dates,
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"next_step_id": "add_schedule"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"schedule_type": "holiday"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"country_code": "DE"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"category": "public"},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Good Friday",
                "holiday_name": "Good Friday",
                "start_offset": 0,
                "end_offset": 0,
                "configuration": "",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_holiday"
    assert result["errors"] == {"base": "schedule_overlap_with_name"}
    assert (
        result["description_placeholders"]["conflicting_schedule"] == "Future Conflict"
    )


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


async def test_edit_schedule_keep_same_name(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test that editing a schedule can keep its name and leaves the others alone."""
    other_schedule = {
        "uid": "schedule-2",
        "name": "Schedule 2",
        "schedule_type": "date",
        "start_month": 12,
        "start_day": 1,
        "end_month": 2,
        "end_day": 28,
    }
    schedules = {
        "schedule-1": {
            "uid": "schedule-1",
            "name": "My Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
        },
        "schedule-2": other_schedule,
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
        {"schedule_id": "schedule-1"},
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
    updated_schedules = result["data"]["services"]["default"]["schedules"]
    assert updated_schedules["schedule-1"]["name"] == "My Schedule"
    assert updated_schedules["schedule-1"]["end_month"] == 9
    assert updated_schedules["schedule-2"] == other_schedule


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


async def test_remove_schedule_flow(hass: HomeAssistant, create_service_entry) -> None:
    """Test removing a schedule confirms with its details and keeps the others."""
    remaining_schedule = {
        "uid": "schedule-2",
        "name": "Schedule 2",
        "schedule_type": "date",
        "start_month": 12,
        "start_day": 1,
        "end_month": 2,
        "end_day": 28,
    }
    entry = create_service_entry(
        schedules={
            "schedule-1": {
                "uid": "schedule-1",
                "name": "Schedule 1",
                "schedule_type": "date",
                "start_month": 6,
                "start_day": 1,
                "end_month": 8,
                "end_day": 31,
            },
            "schedule-2": remaining_schedule,
        }
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
        {"schedule_id": "schedule-1"},
    )
    assert result["step_id"] == "remove_schedule_confirm"
    assert result["description_placeholders"] == {
        "schedule_name": "Schedule 1",
        "schedule_type": "By Date",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"confirm": True},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert get_schedules_from_entry(entry) == {"schedule-2": remaining_schedule}


async def test_remove_schedule_picker_sorted_case_insensitively(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test the schedule picker is sorted by name ignoring case."""
    entry = create_service_entry(
        schedules={
            "schedule_1": {
                "uid": "schedule_1",
                "name": "Summer Schedule",
                "schedule_type": "date",
            },
            "schedule_2": {
                "uid": "schedule_2",
                "name": "Winter Schedule",
                "schedule_type": "date",
            },
            "schedule_3": {
                "uid": "schedule_3",
                "name": "autumn schedule",
                "schedule_type": "week",
            },
        }
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_schedule"},
    )

    assert result["step_id"] == "remove_schedule"
    options = result["data_schema"].schema["schedule_id"].config["options"]
    assert [option["label"] for option in options] == [
        "autumn schedule",
        "Summer Schedule",
        "Winter Schedule",
    ]


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


async def test_edit_nth_day_schedule_first_occurrence(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test editing an existing occurrence-0 nth-day schedule round-trips."""
    schedule_id = "nth-first"
    entry = create_service_entry(
        schedules={
            schedule_id: {
                "uid": schedule_id,
                "name": "First Monday of March",
                "schedule_type": "nth-day",
                "month": 3,
                "occurrence": 0,
                "day_of_week": 0,
                "start_offset": 0,
                "end_offset": 0,
            }
        }
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_id": schedule_id}
    )
    assert result["step_id"] == "configure_nth_day"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "First Monday of March",
            "month": "3",
            "occurrence": "0",
            "day_of_week": "0",
            "start_offset": 1,
            "end_offset": 0,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    schedules = get_schedules_from_entry(entry)
    assert schedules[schedule_id]["occurrence"] == 0
    assert schedules[schedule_id]["start_offset"] == 1


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


async def test_import_holidays_defaults_to_all_holidays_as_holiday_schedules(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test omitting the holiday selection imports every holiday as a holiday schedule."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Independence Day": {
            "pattern": {
                "schedule_type": "date",
                "start_month": 7,
                "start_day": 4,
                "end_month": 7,
                "end_day": 4,
                "description": "Fixed date: July 4",
            },
            "dates": [],
        },
        "Labor Day": {
            "pattern": {
                "schedule_type": "nth-day",
                "month": 9,
                "occurrence": 0,
                "day_of_week": 0,
                "start_offset": 0,
                "end_offset": 0,
                "description": "First Monday of September",
            },
            "dates": [],
        },
    }

    async with _import_holidays_select(hass, entry, mock_holidays) as form:
        result = await hass.config_entries.options.async_configure(form["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    assert {s["name"] for s in schedules.values()} == {"Independence Day", "Labor Day"}
    for schedule in schedules.values():
        assert schedule["schedule_type"] == "holiday"
        assert schedule["country_code"] == "US"
        assert schedule["category"] == "public"
        assert schedule["holiday_name"] == schedule["name"]
        assert schedule["name_lookup"] == "iexact"


async def test_import_holidays_imports_all_selected_categories(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test holidays from several categories are offered and imported together."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Independence Day": {
            "category": "public",
            "pattern": {"schedule_type": "date", "description": "Fixed date: July 4"},
            "dates": [],
        },
        "Bank Holiday": {
            "category": "bank",
            "pattern": {"schedule_type": "date", "description": "Fixed date: May 01"},
            "dates": [],
        },
    }

    async with _import_holidays_select(
        hass, entry, mock_holidays, categories=("public", "bank")
    ) as form:
        result = await hass.config_entries.options.async_configure(form["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    assert {s["name"]: s["category"] for s in schedules.values()} == {
        "Independence Day": "public",
        "Bank Holiday": "bank",
    }


async def test_import_holidays_variable_date_holiday_pattern_kept_as_holiday_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test a movable holiday's own holiday-type pattern is imported as is."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Good Friday": {
            "dates": [date(2026, 4, 3)],
            "pattern": {
                "schedule_type": "holiday",
                "country_code": "US",
                "category": "public",
                "holiday_name": "Good Friday",
                "name_lookup": "iexact",
                "start_offset": 0,
                "end_offset": 0,
                "description": "Holiday-backed (resolved each year)",
            },
        }
    }

    async with _import_holidays_select(hass, entry, mock_holidays) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"], {"use_holiday_type": False}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = next(iter(schedules.values()))
    assert schedule["name"] == "Good Friday"
    assert schedule["schedule_type"] == "holiday"
    assert schedule["country_code"] == "US"
    assert schedule["category"] == "public"
    assert schedule["holiday_name"] == "Good Friday"
    assert "description" not in schedule


async def test_import_holidays_include_country_name(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test importing holidays with country name appended."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {"holidays": ["Holiday A"], "include_country_name": True},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = result["data"]["services"]["default"]["schedules"]
    assert [schedule["name"] for schedule in schedules.values()] == ["Holiday A (US)"]


async def test_import_holidays_none_pattern_with_holiday_type_creates_holiday_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test use_holiday_type bypasses a holiday whose pattern could not be analyzed."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {"Invalid Holiday": {"dates": [], "pattern": None}}

    async with _import_holidays_select(hass, entry, mock_holidays) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {"holidays": ["Invalid Holiday"], "use_holiday_type": True},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 1
    schedule = next(iter(schedules.values()))
    assert schedule["name"] == "Invalid Holiday"
    assert schedule["schedule_type"] == "holiday"
    assert schedule["country_code"] == "US"
    assert schedule["category"] == "public"
    assert schedule["holiday_name"] == "Invalid Holiday"


async def test_import_holidays_none_pattern_without_holiday_type_imports_nothing(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test a holiday without a usable pattern is not imported as a date schedule."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {"Invalid Holiday": {"dates": [], "pattern": None}}

    async with _import_holidays_select(hass, entry, mock_holidays) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {"holidays": ["Invalid Holiday"], "use_holiday_type": False},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_holidays_imported"
    assert get_schedules_from_entry(entry) == {}


async def test_holiday_import_no_holidays_imported(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test no_holidays_imported when all selected holidays are skipped."""
    # Full-year blocking schedule so every holiday import will overlap
    entry = create_service_entry(
        schedules={
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
    )
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
        for i in range(1, 6)
    }

    async with _import_holidays_select(hass, entry, mock_holidays) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"], {"skip_on_overlap": True, "use_holiday_type": False}
        )

    # Details of the skipped holidays are logged, only the key is shown to the user
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_holidays_imported"
    assert list(get_schedules_from_entry(entry)) == ["blocker"]


async def test_import_holidays_skip_overlap_false_imports(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test importing holidays when overlaps are allowed."""
    entry = create_service_entry(
        schedules={
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
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {
                "holidays": ["Holiday A"],
                "skip_on_overlap": False,
                "use_holiday_type": False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = result["data"]["services"]["default"]["schedules"]
    assert sorted(schedule["name"] for schedule in schedules.values()) == [
        "Blocker",
        "Holiday A",
    ]


async def test_import_holidays_overwrite_existing(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test importing holidays overwrites existing schedules."""
    entry = create_service_entry(schedules={"existing-id": _EXISTING_HOLIDAY_A})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {
                "holidays": ["Holiday A"],
                "overwrite_existing": True,
                "use_holiday_type": False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = result["data"]["services"]["default"]["schedules"]
    assert list(schedules.keys()) == ["existing-id"]
    assert schedules["existing-id"]["start_month"] == 7


async def test_import_holidays_overwrite_existing_backfills_missing_uid(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test overwrite updates a stored schedule that has no uid in place.

    Regression test: schedules migrated from v1 may lack a stored uid. The
    overwrite must keep the storage key and take it as the schedule's uid, and
    the old copy (which overlaps the new dates) must not conflict with itself.
    """
    entry = create_service_entry(
        schedules={
            # Deliberately no "uid" keys
            "existing_schedule": {
                "name": "Existing Schedule",
                "schedule_type": "date",
                "start_month": 1,
                "start_day": 1,
                "end_month": 1,
                "end_day": 1,
            },
            "independence_day": {
                "name": "Independence Day",
                "schedule_type": "date",
                "start_month": 7,
                "start_day": 4,
                "end_month": 7,
                "end_day": 4,
            },
        }
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "Independence Day": {
            "pattern": {
                "schedule_type": "date",
                "start_month": 7,
                "start_day": 3,
                "end_month": 7,
                "end_day": 5,
                "description": "July 3-5",
            },
            "dates": [],
        }
    }

    async with _import_holidays_select(hass, entry, mock_holidays) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {
                "holidays": ["Independence Day"],
                "overwrite_existing": True,
                "use_holiday_type": False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    assert set(schedules) == {"existing_schedule", "independence_day"}
    assert schedules["independence_day"]["start_day"] == 3
    assert schedules["independence_day"]["end_day"] == 5
    assert schedules["independence_day"]["uid"] == "independence_day"


async def test_import_holidays_overwrite_existing_with_normalized_name_match(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test importing holidays normalizes names when overwriting existing schedules."""
    entry = create_service_entry(
        schedules={"existing-id": {**_EXISTING_HOLIDAY_A, "name": "  holiday a  "}}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {
                "holidays": ["Holiday A"],
                "overwrite_existing": True,
                "use_holiday_type": False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = result["data"]["services"]["default"]["schedules"]
    assert list(schedules.keys()) == ["existing-id"]
    assert schedules["existing-id"]["name"] == "Holiday A"
    assert schedules["existing-id"]["start_month"] == 7


async def test_import_holidays_skips_existing_with_normalized_name_match(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test importing holidays normalizes names when detecting duplicates."""
    entry = create_service_entry(
        schedules={"existing-id": {**_EXISTING_HOLIDAY_A, "name": "  holiday a  "}}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"], {"holidays": ["Holiday A"]}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_holidays_imported"
    schedules = get_schedules_from_entry(entry)
    assert list(schedules.keys()) == ["existing-id"]
    assert schedules["existing-id"]["name"] == "  holiday a  "


async def test_import_holidays_overwrite_existing_skips_other_overlap(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test overwriting a holiday still respects skip_on_overlap."""
    entry = create_service_entry(
        schedules={"existing-id": _EXISTING_HOLIDAY_A, "blocker-id": _SUMMER_BLOCKER}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {
                "holidays": ["Holiday A"],
                "overwrite_existing": True,
                "use_holiday_type": False,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_holidays_imported"

    schedules = get_schedules_from_entry(entry)
    assert len(schedules) == 2
    assert schedules["existing-id"]["start_month"] == 5
    assert schedules["existing-id"]["start_day"] == 1


async def test_import_holidays_overwrite_existing_allows_other_overlap(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test overwriting a holiday can proceed when overlap skipping is disabled."""
    entry = create_service_entry(
        schedules={"existing-id": _EXISTING_HOLIDAY_A, "blocker-id": _SUMMER_BLOCKER}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {
                "holidays": ["Holiday A"],
                "skip_on_overlap": False,
                "overwrite_existing": True,
                "use_holiday_type": False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY

    schedules = result["data"]["services"]["default"]["schedules"]
    assert len(schedules) == 2
    assert schedules["existing-id"]["start_month"] == 7
    assert schedules["existing-id"]["start_day"] == 4
    assert schedules["blocker-id"]["name"] == "Summer Blocker"


async def test_import_holidays_partial_success_after_skipped_overwrite(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test later holidays still import after an earlier overwrite is skipped."""
    entry = create_service_entry(
        schedules={"existing-id": _EXISTING_HOLIDAY_A, "blocker-id": _SUMMER_BLOCKER}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        **_HOLIDAY_A_JULY_4,
        "Labor Day": {
            "pattern": {
                "schedule_type": "nth-day",
                "month": 9,
                "occurrence": 0,
                "day_of_week": 0,
                "start_offset": 0,
                "end_offset": 0,
                "description": "Labor Day",
            },
            "dates": [date(2026, 9, 7)],
        },
    }

    async with _import_holidays_select(hass, entry, mock_holidays) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {
                "holidays": ["Holiday A", "Labor Day"],
                "overwrite_existing": True,
                "use_holiday_type": False,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY

    schedules = result["data"]["services"]["default"]["schedules"]
    assert len(schedules) == 3
    assert schedules["existing-id"]["start_month"] == 5
    assert schedules["existing-id"]["start_day"] == 1
    assert schedules["blocker-id"]["name"] == "Summer Blocker"
    assert any(schedule["name"] == "Labor Day" for schedule in schedules.values())


async def test_import_holidays_no_holidays_selected(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test import holidays requires at least one holiday selection."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        result = await hass.config_entries.options.async_configure(
            form["flow_id"], {"holidays": []}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"holidays": "no_holidays_selected"}
    assert get_schedules_from_entry(entry) == {}


async def test_import_holidays_stale_selection_not_found(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test import holidays handles a stale selection that is no longer available."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async with _import_holidays_select(hass, entry, _HOLIDAY_A_JULY_4) as form:
        flow = hass.config_entries.options._progress[form["flow_id"]]
        result = await flow._import_selected_holidays(
            ["Missing Holiday"],
            overwrite_existing=False,
            skip_on_overlap=True,
            include_country_name=False,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_holidays_imported"
    assert get_schedules_from_entry(entry) == {}


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


async def test_options_flow_add_date_schedule_with_configuration(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test adding a date schedule with YAML configuration."""
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
            "name": "Configured Schedule",
            "start_month": "2",
            "start_day": 1,
            "end_month": "3",
            "end_day": 15,
            "configuration": "color: red\nbrightness: 75",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    schedule = next(iter(schedules.values()))
    assert schedule["configuration"] == {"color": "red", "brightness": 75}


async def test_options_flow_invalid_yaml_non_dict(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test scalar YAML is rejected for schedule configuration.

    Lists and dicts are valid YAML structures and are accepted; only simple
    scalar values must be rejected.
    """
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
            "name": "Bad Config Schedule",
            "start_month": "1",
            "start_day": 1,
            "end_month": "12",
            "end_day": 31,
            "configuration": "just a string",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_yaml_with_details"
    assert "YAML structure" in result["description_placeholders"]["details"]


async def test_default_configuration_invalid_yaml_non_dict(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test scalar YAML is rejected for default configuration."""
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
        {"configuration": "just a string"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_yaml_with_details"
    assert "YAML structure" in result["description_placeholders"]["details"]


async def test_options_flow_list_configuration_accepted(
    hass: HomeAssistant, create_service_entry
) -> None:
    """A list-structured YAML configuration is accepted and stored."""
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
            "name": "List Config Schedule",
            "start_month": "1",
            "start_day": 1,
            "end_month": "12",
            "end_day": 31,
            "configuration": "- one\n- two",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    schedule = next(iter(schedules.values()))
    assert schedule["configuration"] == ["one", "two"]


async def test_options_flow_list_configuration_round_trips_in_edit_form(
    hass: HomeAssistant, create_service_entry
) -> None:
    """A stored list configuration is rendered back as YAML in the edit form."""
    schedules = {
        "test-id": {
            "uid": "test-id",
            "name": "List Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "configuration": ["one", "two"],
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"show_advanced_options": False}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "edit_schedule"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"schedule_id": "test-id"},
    )
    assert result["step_id"] == "configure_date"

    schema = result["data_schema"].schema
    config_key = next(key for key in schema if str(key) == "configuration")
    # The list must be rendered as YAML, not as a Python repr.
    assert config_key.default() == "- one\n- two"


async def test_options_flow_explicit_empty_dict_configuration_stored(
    hass: HomeAssistant, create_service_entry
) -> None:
    """An explicit empty dict configuration is stored, not silently dropped."""
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
            "name": "Empty Config Schedule",
            "start_month": "1",
            "start_day": 1,
            "end_month": "12",
            "end_day": 31,
            "configuration": "{}",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    schedule = next(iter(schedules.values()))
    assert "configuration" in schedule
    assert schedule["configuration"] == {}


async def test_options_flow_add_week_schedule_whole_week_no_types(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test week schedule without week types or day filters."""
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
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Whole Week Schedule",
            "start_month": "1",
            "start_week": "1",
            "start_day_of_week": "",
            "end_month": "2",
            "end_week": "4",
            "end_day_of_week": "",
            "configuration": "",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    schedule = next(iter(schedules.values()))
    assert schedule["start_week"] == 1
    assert schedule["end_week"] == 4
    assert "start_week_type" not in schedule
    assert "end_week_type" not in schedule
    assert "start_day_of_week" not in schedule
    assert "end_day_of_week" not in schedule


async def test_holiday_selection_schema_without_holiday_data(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test holiday selection schema with missing holiday data."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow = hass.config_entries.options._progress[result["flow_id"]]
    result = await flow.async_step_import_holidays_select()

    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    holiday_selector = next(
        value for key, value in schema.items() if str(key) == "holidays"
    )
    assert holiday_selector.config["options"] == []


async def test_holiday_selection_schema_fetch_error(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test holiday selection schema when fetching holidays fails."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow = hass.config_entries.options._progress[result["flow_id"]]
    flow._holiday_data = {"country": "US", "categories": ["public"]}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
        new=AsyncMock(side_effect=Exception("boom")),
    ):
        result = await flow.async_step_import_holidays_select()

    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    holiday_selector = next(
        value for key, value in schema.items() if str(key) == "holidays"
    )
    assert holiday_selector.config["options"] == []


async def test_import_holidays_categories_error(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test import holidays aborts when categories cannot be loaded."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"US": "United States"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(side_effect=Exception("boom")),
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "import_holidays"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"country": "US"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "import_error"


async def test_import_holidays_missing_country(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test import holidays aborts when country is missing."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow = hass.config_entries.options._progress[result["flow_id"]]
    flow._holiday_data = {"categories": ["public"]}

    result = await flow.async_step_import_holidays_select(
        {
            "holidays": ["Holiday A"],
        }
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "import_error"


async def test_default_configuration_clear_with_single_space(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test clearing default configuration using a single space."""
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
        {"configuration": "key: value"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "default_configuration"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"configuration": " "},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["services"]["default"]["configuration"] == {}
