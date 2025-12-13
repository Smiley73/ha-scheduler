"""Test the Scheduler calendar."""

from datetime import date, datetime

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_calendar_with_date_schedule(hass: HomeAssistant) -> None:
    """Test calendar entity with a date-based schedule."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "schedules": {
                "test-schedule-1": {
                    "name": "Summer Schedule",
                    "schedule_type": "date",
                    "start_month": 6,
                    "start_day": 1,
                    "end_month": 8,
                    "end_day": 31,
                    "uid": "test-schedule-1",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the calendar entity
    state = hass.states.get("calendar.test_scheduler")
    assert state is not None
    assert state.attributes.get("friendly_name") == "Test Scheduler"

    # Get calendar entity
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events for summer 2024
    start = datetime(2024, 5, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 9, 30, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Summer Schedule"
    assert events[0].start == date(2024, 6, 1)
    assert events[0].end == date(2024, 9, 1)  # End date + 1 day for all-day events


async def test_calendar_with_week_schedule(hass: HomeAssistant) -> None:
    """Test calendar entity with a week-based schedule."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "schedules": {
                "test-schedule-1": {
                    "name": "Week Schedule",
                    "schedule_type": "week",
                    "start_month": 3,
                    "start_week": 0,  # First
                    "start_day_of_week": 0,  # Monday
                    "end_month": 3,
                    "end_week": 4,  # Last
                    "end_day_of_week": 4,  # Friday
                    "uid": "test-schedule-1",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get calendar entity
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events for March 2024
    start = datetime(2024, 3, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 3, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Week Schedule"
    # First Monday of March 2024 is March 4
    assert events[0].start == date(2024, 3, 4)
    # Last Friday of March 2024 is March 29, +1 day = March 30
    assert events[0].end == date(2024, 3, 30)


async def test_calendar_with_nth_day_schedule(hass: HomeAssistant) -> None:
    """Test calendar entity with an nth-day schedule."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "schedules": {
                "test-schedule-1": {
                    "name": "Nth Day Schedule",
                    "schedule_type": "nth-day",
                    "month": 3,
                    "occurrence": 1,  # Second
                    "day_of_week": 1,  # Tuesday
                    "start_offset": 2,
                    "end_offset": 3,
                    "uid": "test-schedule-1",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get calendar entity
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events for March 2024
    start = datetime(2024, 3, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 3, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Nth Day Schedule"
    # Second Tuesday of March 2024 is March 12, -2 days = March 10
    assert events[0].start == date(2024, 3, 10)
    # March 12 + 3 days = March 15, +1 day for all-day = March 16
    assert events[0].end == date(2024, 3, 16)


async def test_calendar_with_configuration(hass: HomeAssistant, freezer) -> None:
    """Test calendar entity with schedule configuration."""
    # Set date to June 15, 2024 (within the schedule period)
    freezer.move_to("2024-06-15 12:00:00")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "configuration": {"default_key": "default_value"},
            "schedules": {
                "test-schedule-1": {
                    "name": "Schedule with Config",
                    "schedule_type": "date",
                    "start_month": 6,
                    "start_day": 1,
                    "end_month": 6,
                    "end_day": 30,
                    "uid": "test-schedule-1",
                    "configuration": {"custom_key": "custom_value"},
                }
            },
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check default configuration attribute
    state = hass.states.get("calendar.test_scheduler")
    assert state.attributes.get("default_configuration") == {
        "default_key": "default_value"
    }

    # Check that description field contains the formatted configuration
    assert state.attributes.get("description") == "custom_key: custom_value"

    # Get calendar entity
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events
    start = datetime(2024, 6, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 6, 30, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    # Configuration should be in description as formatted string
    assert events[0].description == "custom_key: custom_value"


async def test_calendar_multiple_schedules(hass: HomeAssistant) -> None:
    """Test calendar entity with multiple schedules."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "schedules": {
                "schedule-1": {
                    "name": "Schedule 1",
                    "schedule_type": "date",
                    "start_month": 1,
                    "start_day": 1,
                    "end_month": 3,
                    "end_day": 31,
                    "uid": "schedule-1",
                },
                "schedule-2": {
                    "name": "Schedule 2",
                    "schedule_type": "date",
                    "start_month": 6,
                    "start_day": 1,
                    "end_month": 8,
                    "end_day": 31,
                    "uid": "schedule-2",
                },
            }
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get calendar entity
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events for entire year
    start = datetime(2024, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 12, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 2
    assert events[0].summary == "Schedule 1"
    assert events[1].summary == "Schedule 2"
