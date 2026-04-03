"""Test diagnostics for Scheduler integration."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.ha_scheduler.diagnostics import (
    async_get_config_entry_diagnostics,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_diagnostics_empty_schedules(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test diagnostics with no schedules."""
    entry = create_service_entry()
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["title"] == "Test Scheduler"
    assert diagnostics["entry"]["scheduler_name"] == "Test Scheduler"
    assert diagnostics["summary"]["total_services"] == 1
    assert diagnostics["summary"]["total_schedules"] == 0

    default_service = diagnostics["services"]["default"]
    assert default_service["name"] == "Test Scheduler"
    assert default_service["schedules"]["count"] == 0
    assert default_service["schedules"]["items"] == []
    assert default_service["default_configuration"]["has_configuration"] is False


async def test_diagnostics_with_date_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["summary"]["total_schedules"] == 1

    default_service = diagnostics["services"]["default"]
    assert default_service["schedules"]["count"] == 1
    assert len(default_service["schedules"]["items"]) == 1

    schedule = default_service["schedules"]["items"][0]
    assert schedule["name"] == "Summer Schedule"
    assert schedule["type"] == "date"
    assert schedule["start_month"] == 6
    assert schedule["start_day"] == 1
    assert schedule["end_month"] == 8
    assert schedule["end_day"] == 31
    assert schedule["has_configuration"] is False


async def test_diagnostics_with_week_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["summary"]["total_schedules"] == 1
    default_service = diagnostics["services"]["default"]
    schedule = default_service["schedules"]["items"][0]
    assert schedule["name"] == "Week Schedule"
    assert schedule["type"] == "week"
    assert schedule["start_week"] == 0
    assert schedule["end_week"] == 4


async def test_diagnostics_with_nth_day_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["summary"]["total_schedules"] == 1
    default_service = diagnostics["services"]["default"]
    schedule = default_service["schedules"]["items"][0]
    assert schedule["name"] == "Nth Day Schedule"
    assert schedule["type"] == "nth-day"
    assert schedule["month"] == 3
    assert schedule["occurrence"] == 2
    assert schedule["day_of_week"] == 1


async def test_diagnostics_with_holiday_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test diagnostics with a holiday-backed schedule."""
    schedule_data = {
        "schedule-holiday": {
            "name": "Good Friday",
            "schedule_type": "holiday",
            "country_code": "DE",
            "category": "public",
            "holiday_name": "Karfreitag",
            "name_lookup": "iexact",
            "start_offset": 1,
            "end_offset": 2,
            "uid": "schedule-holiday",
        }
    }
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["summary"]["total_schedules"] == 1
    default_service = diagnostics["services"]["default"]
    schedule = default_service["schedules"]["items"][0]
    assert schedule["name"] == "Good Friday"
    assert schedule["type"] == "holiday"
    assert schedule["country_code"] == "DE"
    assert schedule["category"] == "public"
    assert schedule["holiday_name"] == "Karfreitag"
    assert schedule["name_lookup"] == "iexact"
    assert schedule["start_offset"] == 1
    assert schedule["end_offset"] == 2


async def test_diagnostics_prime_holiday_cache(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test diagnostics primes holiday caches before generating holiday dates."""
    schedule_data = {
        "schedule-holiday": {
            "name": "Good Friday",
            "schedule_type": "holiday",
            "country_code": "DE",
            "category": "public",
            "holiday_name": "Karfreitag",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
            "uid": "schedule-holiday",
        }
    }
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_scheduler.diagnostics.async_prime_holiday_cache",
        new=AsyncMock(),
    ) as mock_prime_holiday_cache:
        await async_get_config_entry_diagnostics(hass, entry)

    mock_prime_holiday_cache.assert_awaited_once()


async def test_diagnostics_with_configuration(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    default_service = diagnostics["services"]["default"]
    schedule = default_service["schedules"]["items"][0]
    assert schedule["has_configuration"] is True
    assert schedule["configuration"]["summary"] == "Test Event"
    assert schedule["configuration"]["description"] == "Test Description"


async def test_diagnostics_with_default_configuration(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test diagnostics with default configuration."""
    default_config = {
        "summary": "Default Event",
        "location": "Home",
    }
    entry = create_service_entry(configuration=default_config)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    default_service = diagnostics["services"]["default"]
    assert default_service["default_configuration"]["has_configuration"] is True
    assert (
        default_service["default_configuration"]["configuration"]["summary"]
        == "Default Event"
    )
    assert (
        default_service["default_configuration"]["configuration"]["location"] == "Home"
    )


async def test_diagnostics_multiple_schedules(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["summary"]["total_schedules"] == 2
    default_service = diagnostics["services"]["default"]
    assert default_service["schedules"]["count"] == 2
    assert len(default_service["schedules"]["items"]) == 2

    names = {s["name"] for s in default_service["schedules"]["items"]}
    assert names == {"Schedule 1", "Schedule 2"}


async def test_diagnostics_includes_future_dates(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    default_service = diagnostics["services"]["default"]
    schedule = default_service["schedules"]["items"][0]
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


async def test_diagnostics_day_names_week_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    default_service = diagnostics["services"]["default"]
    schedule = default_service["schedules"]["items"][0]
    assert schedule["start_day_of_week"] == 0
    assert schedule["start_day_name"] == "Monday"
    assert schedule["end_day_of_week"] == 4
    assert schedule["end_day_name"] == "Friday"


async def test_diagnostics_day_names_nth_day_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedule_data)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    default_service = diagnostics["services"]["default"]
    schedule = default_service["schedules"]["items"][0]
    assert schedule["day_of_week"] == 3
    assert schedule["day_name"] == "Thursday"
