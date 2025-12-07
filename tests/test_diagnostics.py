"""Test diagnostics for Scheduler integration."""

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.scheduler.const import DOMAIN
from custom_components.scheduler.diagnostics import async_get_config_entry_diagnostics

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
