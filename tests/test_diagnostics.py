"""Test diagnostics for Scheduler integration."""

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN
from custom_components.ha_scheduler.diagnostics import (
    async_get_config_entry_diagnostics,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_diagnostics_empty_schedules(hass: HomeAssistant) -> None:
    """Test diagnostics with no schedules."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["title"] == "Test Scheduler"
    assert diagnostics["schedules"]["count"] == 0
    assert diagnostics["schedules"]["items"] == []
    assert diagnostics["default_configuration"]["has_default"] is False


async def test_diagnostics_with_date_schedule(hass: HomeAssistant) -> None:
    """Test diagnostics with a date-based schedule."""
    schedule_data = {
        "schedule-1": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "schedule-1",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["schedules"]["count"] == 1
    assert len(diagnostics["schedules"]["items"]) == 1

    schedule = diagnostics["schedules"]["items"][0]
    assert schedule["name"] == "Summer Schedule"
    assert schedule["type"] == "date"
    assert schedule["start_month"] == 6
    assert schedule["start_day"] == 1
    assert schedule["end_month"] == 8
    assert schedule["end_day"] == 31
    assert schedule["has_configuration"] is False


async def test_diagnostics_with_week_schedule(hass: HomeAssistant) -> None:
    """Test diagnostics with a week-based schedule."""
    schedule_data = {
        "schedule-2": {
            "name": "Week Schedule",
            "schedule_type": "week",
            "start_month": 1,
            "start_week": 0,
            "start_day_of_week": 0,
            "end_month": 12,
            "end_week": 4,
            "end_day_of_week": 6,
            "uid": "schedule-2",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["schedules"]["count"] == 1
    schedule = diagnostics["schedules"]["items"][0]
    assert schedule["name"] == "Week Schedule"
    assert schedule["type"] == "week"
    assert schedule["start_week"] == 0
    assert schedule["end_week"] == 4


async def test_diagnostics_with_nth_day_schedule(hass: HomeAssistant) -> None:
    """Test diagnostics with an nth-day schedule."""
    schedule_data = {
        "schedule-3": {
            "name": "Nth Day Schedule",
            "schedule_type": "nth-day",
            "month": 3,
            "occurrence": 2,
            "day_of_week": 1,
            "start_offset": 0,
            "end_offset": 7,
            "uid": "schedule-3",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["schedules"]["count"] == 1
    schedule = diagnostics["schedules"]["items"][0]
    assert schedule["name"] == "Nth Day Schedule"
    assert schedule["type"] == "nth-day"
    assert schedule["month"] == 3
    assert schedule["occurrence"] == 2
    assert schedule["day_of_week"] == 1


async def test_diagnostics_with_configuration(hass: HomeAssistant) -> None:
    """Test diagnostics with schedule configuration."""
    schedule_data = {
        "schedule-4": {
            "name": "Configured Schedule",
            "schedule_type": "date",
            "start_month": 1,
            "start_day": 1,
            "end_month": 12,
            "end_day": 31,
            "uid": "schedule-4",
            "configuration": {
                "summary": "Test Event",
                "description": "Test Description",
            },
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    schedule = diagnostics["schedules"]["items"][0]
    assert schedule["has_configuration"] is True
    assert schedule["configuration"]["summary"] == "Test Event"
    assert schedule["configuration"]["description"] == "Test Description"


async def test_diagnostics_with_default_configuration(hass: HomeAssistant) -> None:
    """Test diagnostics with default configuration."""
    default_config = {
        "summary": "Default Event",
        "location": "Home",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "schedules": {},
            "configuration": default_config,
        },
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["default_configuration"]["has_default"] is True
    assert (
        diagnostics["default_configuration"]["configuration"]["summary"]
        == "Default Event"
    )
    assert diagnostics["default_configuration"]["configuration"]["location"] == "Home"


async def test_diagnostics_multiple_schedules(hass: HomeAssistant) -> None:
    """Test diagnostics with multiple schedules."""
    schedule_data = {
        "schedule-1": {
            "name": "Schedule 1",
            "schedule_type": "date",
            "start_month": 1,
            "start_day": 1,
            "end_month": 6,
            "end_day": 30,
            "uid": "schedule-1",
        },
        "schedule-2": {
            "name": "Schedule 2",
            "schedule_type": "week",
            "start_month": 7,
            "start_week": 0,
            "start_day_of_week": 0,
            "end_month": 12,
            "end_week": 4,
            "end_day_of_week": 6,
            "uid": "schedule-2",
        },
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["schedules"]["count"] == 2
    assert len(diagnostics["schedules"]["items"]) == 2

    names = {s["name"] for s in diagnostics["schedules"]["items"]}
    assert names == {"Schedule 1", "Schedule 2"}


async def test_diagnostics_includes_future_dates(hass: HomeAssistant) -> None:
    """Test that diagnostics includes future date calculations."""
    schedule_data = {
        "schedule-1": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "schedule-1",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    schedule = diagnostics["schedules"]["items"][0]
    assert "future_dates" in schedule

    future_dates = schedule["future_dates"]
    assert "years" in future_dates
    assert "warnings" in future_dates

    # Should have 3 years of data
    assert len(future_dates["years"]) == 3

    # Each year should have the expected structure
    for year_data in future_dates["years"].values():
        if "error" not in year_data:
            assert "start_date" in year_data
            assert "end_date" in year_data
            assert "duration_days" in year_data

            # For this date schedule, duration should be 92 days (June 1 - Aug 31)
            assert year_data["duration_days"] == 92


async def test_diagnostics_handles_invalid_schedule(hass: HomeAssistant) -> None:
    """Test that diagnostics handles invalid schedules gracefully."""
    schedule_data = {
        "schedule-invalid": {
            "name": "Invalid Schedule",
            "schedule_type": "invalid_type",
            "uid": "schedule-invalid",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    schedule = diagnostics["schedules"]["items"][0]
    future_dates = schedule["future_dates"]

    # Should have warnings for all years
    assert len(future_dates["warnings"]) == 3

    # Each year should have error information
    for year_data in future_dates["years"].values():
        assert "error" in year_data
        assert year_data["start_date"] is None
        assert year_data["end_date"] is None
        assert year_data["duration_days"] is None


async def test_diagnostics_nth_day_schedule_dates(hass: HomeAssistant) -> None:
    """Test diagnostics with nth-day schedule shows varying dates."""
    schedule_data = {
        "schedule-thanksgiving": {
            "name": "Thanksgiving",
            "schedule_type": "nth-day",
            "month": 11,
            "occurrence": 3,  # Fourth occurrence (0-indexed)
            "day_of_week": 3,  # Thursday
            "start_offset": 0,
            "end_offset": 0,
            "uid": "schedule-thanksgiving",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    schedule = diagnostics["schedules"]["items"][0]
    future_dates = schedule["future_dates"]

    # Should have no warnings for valid schedule
    assert len(future_dates["warnings"]) == 0

    # Each year should have valid dates
    dates_by_year = {}
    for year, year_data in future_dates["years"].items():
        assert "error" not in year_data
        assert year_data["duration_days"] == 1  # Single day event
        dates_by_year[year] = year_data["start_date"]

    # Dates should be different each year (Thanksgiving moves around)
    all_dates = list(dates_by_year.values())
    assert len(set(all_dates)) == len(
        all_dates
    ), "All Thanksgiving dates should be different"


async def test_diagnostics_year_wrapping_schedule(hass: HomeAssistant) -> None:
    """Test diagnostics with schedule that wraps across years."""
    schedule_data = {
        "schedule-winter": {
            "name": "Winter Schedule",
            "schedule_type": "date",
            "start_month": 12,
            "start_day": 15,
            "end_month": 1,
            "end_day": 15,
            "uid": "schedule-winter",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    schedule = diagnostics["schedules"]["items"][0]
    future_dates = schedule["future_dates"]

    # Should have no warnings for valid schedule
    assert len(future_dates["warnings"]) == 0

    # Each year should have valid dates spanning year boundary
    for year, year_data in future_dates["years"].items():
        assert "error" not in year_data
        assert year_data["duration_days"] == 32  # Dec 15 to Jan 15 (32 days)

        # Start date should be in December of the year
        start_date = year_data["start_date"]
        assert start_date.startswith(f"{year}-12-15")

        # End date should be in January of the next year
        end_date = year_data["end_date"]
        next_year = str(int(year) + 1)
        assert end_date.startswith(f"{next_year}-01-15")


async def test_diagnostics_day_names_week_schedule(hass: HomeAssistant) -> None:
    """Test that week schedules include day names alongside day numbers."""
    schedule_data = {
        "schedule-week": {
            "name": "Week Schedule with Day Names",
            "schedule_type": "week",
            "start_month": 3,
            "start_week": 0,  # First week
            "start_day_of_week": 0,  # Monday
            "end_month": 3,
            "end_week": 2,  # Third week
            "end_day_of_week": 4,  # Friday
            "uid": "schedule-week",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    schedule = diagnostics["schedules"]["items"][0]
    assert schedule["start_day_of_week"] == 0
    assert schedule["start_day_name"] == "Monday"
    assert schedule["end_day_of_week"] == 4
    assert schedule["end_day_name"] == "Friday"


async def test_diagnostics_day_names_nth_day_schedule(hass: HomeAssistant) -> None:
    """Test that nth-day schedules include day names alongside day numbers."""
    schedule_data = {
        "schedule-thanksgiving": {
            "name": "Thanksgiving with Day Name",
            "schedule_type": "nth-day",
            "month": 11,
            "occurrence": 3,  # Fourth occurrence (0-indexed)
            "day_of_week": 3,  # Thursday
            "start_offset": 0,
            "end_offset": 0,
            "uid": "schedule-thanksgiving",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    schedule = diagnostics["schedules"]["items"][0]
    assert schedule["day_of_week"] == 3
    assert schedule["day_name"] == "Thursday"


async def test_diagnostics_day_names_all_days(hass: HomeAssistant) -> None:
    """Test day name mapping for all days of the week."""
    expected_mappings = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    for day_num, expected_name in expected_mappings:
        schedule_data = {
            f"schedule-{day_num}": {
                "name": f"Schedule for {expected_name}",
                "schedule_type": "nth-day",
                "month": 6,
                "occurrence": 0,  # First occurrence
                "day_of_week": day_num,
                "start_offset": 0,
                "end_offset": 0,
                "uid": f"schedule-{day_num}",
            }
        }
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Scheduler",
            data={},
            options={"schedules": schedule_data},
        )
        entry.add_to_hass(hass)

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        schedule = diagnostics["schedules"]["items"][0]

        assert schedule["day_of_week"] == day_num
        assert schedule["day_name"] == expected_name


async def test_diagnostics_day_names_invalid_values(hass: HomeAssistant) -> None:
    """Test that invalid day_of_week values return None for day names."""
    schedule_data = {
        "schedule-invalid": {
            "name": "Invalid Day Schedule",
            "schedule_type": "nth-day",
            "month": 6,
            "occurrence": 0,
            "day_of_week": 7,  # Invalid - should be 0-6
            "start_offset": 0,
            "end_offset": 0,
            "uid": "schedule-invalid",
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    schedule = diagnostics["schedules"]["items"][0]
    assert schedule["day_of_week"] == 7
    assert schedule["day_name"] is None


async def test_diagnostics_overlap_detection_no_conflicts(hass: HomeAssistant) -> None:
    """Test that diagnostics correctly identifies no conflicts between schedules."""
    schedule_data = {
        "schedule-1": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "schedule-1",
        },
        "schedule-2": {
            "name": "Winter Schedule",
            "schedule_type": "date",
            "start_month": 12,
            "start_day": 1,
            "end_month": 2,
            "end_day": 28,
            "uid": "schedule-2",
        },
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Check both schedules for no conflicts
    for schedule in diagnostics["schedules"]["items"]:
        future_dates = schedule["future_dates"]
        for year_data in future_dates["years"].values():
            if "error" not in year_data:
                assert "overlaps" in year_data
                overlaps = year_data["overlaps"]
                assert overlaps["status"] == "no_conflicts"
                assert overlaps["conflict_count"] == 0
                assert overlaps["conflicting_schedules"] == []


async def test_diagnostics_overlap_detection_with_conflicts(
    hass: HomeAssistant,
) -> None:
    """Test that diagnostics correctly identifies conflicts between schedules."""
    schedule_data = {
        "schedule-1": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "schedule-1",
        },
        "schedule-2": {
            "name": "Overlapping Summer",
            "schedule_type": "date",
            "start_month": 7,
            "start_day": 15,
            "end_month": 9,
            "end_day": 15,
            "uid": "schedule-2",
        },
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Check first schedule for conflicts with second
    schedule_1 = next(
        s for s in diagnostics["schedules"]["items"] if s["name"] == "Summer Schedule"
    )
    future_dates = schedule_1["future_dates"]

    for year_data in future_dates["years"].values():
        if "error" not in year_data:
            assert "overlaps" in year_data
            overlaps = year_data["overlaps"]
            assert overlaps["status"] == "conflicts_found"
            assert overlaps["conflict_count"] == 1
            assert len(overlaps["conflicting_schedules"]) == 1

            conflict = overlaps["conflicting_schedules"][0]
            assert conflict["name"] == "Overlapping Summer"
            assert conflict["id"] == "schedule-2"
            assert "overlap_start" in conflict
            assert "overlap_end" in conflict


async def test_diagnostics_overlap_detection_multiple_conflicts(
    hass: HomeAssistant,
) -> None:
    """Test that diagnostics correctly identifies multiple conflicts."""
    schedule_data = {
        "schedule-main": {
            "name": "Main Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "schedule-main",
        },
        "schedule-overlap1": {
            "name": "Overlap 1",
            "schedule_type": "date",
            "start_month": 5,
            "start_day": 15,
            "end_month": 6,
            "end_day": 15,
            "uid": "schedule-overlap1",
        },
        "schedule-overlap2": {
            "name": "Overlap 2",
            "schedule_type": "date",
            "start_month": 8,
            "start_day": 15,
            "end_month": 9,
            "end_day": 15,
            "uid": "schedule-overlap2",
        },
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Check main schedule for conflicts with both others
    main_schedule = next(
        s for s in diagnostics["schedules"]["items"] if s["name"] == "Main Schedule"
    )
    future_dates = main_schedule["future_dates"]

    for year_data in future_dates["years"].values():
        if "error" not in year_data:
            assert "overlaps" in year_data
            overlaps = year_data["overlaps"]
            assert overlaps["status"] == "conflicts_found"
            assert overlaps["conflict_count"] == 2
            assert len(overlaps["conflicting_schedules"]) == 2

            conflict_names = {c["name"] for c in overlaps["conflicting_schedules"]}
            assert conflict_names == {"Overlap 1", "Overlap 2"}


async def test_diagnostics_overlap_detection_nth_day_schedules(
    hass: HomeAssistant,
) -> None:
    """Test overlap detection with nth-day schedules that vary by year."""
    schedule_data = {
        "thanksgiving": {
            "name": "Thanksgiving",
            "schedule_type": "nth-day",
            "month": 11,
            "occurrence": 3,  # Fourth Thursday
            "day_of_week": 3,  # Thursday
            "start_offset": 0,
            "end_offset": 3,  # 4-day weekend
            "uid": "thanksgiving",
        },
        "black-friday": {
            "name": "Black Friday Sale",
            "schedule_type": "nth-day",
            "month": 11,
            "occurrence": 3,  # Fourth Thursday
            "day_of_week": 3,  # Thursday
            "start_offset": 1,  # Start Friday
            "end_offset": 1,  # End Friday
            "uid": "black-friday",
        },
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedule_data},
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Check Thanksgiving schedule for conflicts with Black Friday
    thanksgiving = next(
        s for s in diagnostics["schedules"]["items"] if s["name"] == "Thanksgiving"
    )
    future_dates = thanksgiving["future_dates"]

    for year_data in future_dates["years"].values():
        if "error" not in year_data:
            assert "overlaps" in year_data
            overlaps = year_data["overlaps"]
            assert overlaps["status"] == "conflicts_found"
            assert overlaps["conflict_count"] == 1

            conflict = overlaps["conflicting_schedules"][0]
            assert conflict["name"] == "Black Friday Sale"
