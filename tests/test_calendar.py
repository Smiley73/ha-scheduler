"""Test the Scheduler calendar."""

from datetime import date, datetime

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
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


async def test_calendar_with_date_schedule(hass: HomeAssistant) -> None:
    """Test calendar entity with a date-based schedule."""
    schedules = {
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
    entry = _create_service_entry(schedules=schedules)
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
    schedules = {
        "test-schedule-1": {
            "name": "Week Schedule",
            "schedule_type": "week",
            "start_month": 3,
            "start_week": 1,  # Second week (has Monday)
            "start_day_of_week": 0,  # Monday
            "end_month": 3,
            "end_week": 4,  # Last week (has Friday)
            "end_day_of_week": 4,  # Friday
            "uid": "test-schedule-1",
        }
    }
    entry = _create_service_entry(schedules=schedules)
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
    # Monday of second week of March 2024 is March 4
    assert events[0].start == date(2024, 3, 4)
    # Friday of last week of March 2024 is March 29, +1 day = March 30
    assert events[0].end == date(2024, 3, 30)


async def test_calendar_with_nth_day_schedule(hass: HomeAssistant) -> None:
    """Test calendar entity with an nth-day schedule."""
    schedules = {
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
    entry = _create_service_entry(schedules=schedules)
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

    schedules = {
        "test-schedule-1": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "test-schedule-1",
            "configuration": {
                "summary": "Custom Summer Event",
                "description": "Summer vacation period",
            },
        }
    }
    entry = _create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the calendar entity
    calendar_entity = None
    for entity in hass.data["calendar"].entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar_entity = entity
            break

    assert calendar_entity is not None

    # Check current event (should be active on June 15)
    current_event = calendar_entity.event
    assert current_event is not None
    assert current_event.summary == "Summer Schedule"

    # Check extra state attributes
    attrs = calendar_entity.extra_state_attributes
    assert attrs["name"] == "Summer Schedule"
    assert attrs["configuration"]["summary"] == "Custom Summer Event"
    assert attrs["configuration"]["description"] == "Summer vacation period"


async def test_calendar_multiple_schedules(hass: HomeAssistant) -> None:
    """Test calendar entity with multiple schedules."""
    schedules = {
        "schedule-1": {
            "name": "Spring Schedule",
            "schedule_type": "date",
            "start_month": 3,
            "start_day": 1,
            "end_month": 5,
            "end_day": 31,
            "uid": "schedule-1",
        },
        "schedule-2": {
            "name": "Fall Schedule",
            "schedule_type": "date",
            "start_month": 9,
            "start_day": 1,
            "end_month": 11,
            "end_day": 30,
            "uid": "schedule-2",
        },
    }
    entry = _create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get calendar entity
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events for entire 2024
    start = datetime(2024, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 12, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 2

    # Sort events by start date
    events.sort(key=lambda e: e.start)

    # Spring schedule
    assert events[0].summary == "Spring Schedule"
    assert events[0].start == date(2024, 3, 1)
    assert events[0].end == date(2024, 6, 1)  # May 31 + 1 day

    # Fall schedule
    assert events[1].summary == "Fall Schedule"
    assert events[1].start == date(2024, 9, 1)
    assert events[1].end == date(2024, 12, 1)  # November 30 + 1 day


async def test_calendar_with_default_configuration(
    hass: HomeAssistant, freezer
) -> None:
    """Test calendar entity with default configuration."""
    # Set date to June 15, 2024 (within the schedule period)
    freezer.move_to("2024-06-15 12:00:00")

    schedules = {
        "test-schedule-1": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "test-schedule-1",
            # No schedule-specific configuration
        }
    }

    default_config = {
        "summary": "Default Event",
        "location": "Home",
    }

    entry = _create_service_entry(schedules=schedules, configuration=default_config)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the calendar entity
    calendar_entity = None
    for entity in hass.data["calendar"].entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar_entity = entity
            break

    assert calendar_entity is not None

    # Check extra state attributes
    attrs = calendar_entity.extra_state_attributes
    assert attrs["name"] == "Summer Schedule"
    assert attrs["configuration"]["summary"] == "Default Event"
    assert attrs["configuration"]["location"] == "Home"
    assert attrs["default_configuration"]["summary"] == "Default Event"


async def test_calendar_year_wrapping_schedule(hass: HomeAssistant) -> None:
    """Test calendar entity with year-wrapping schedule."""
    schedules = {
        "winter-schedule": {
            "name": "Winter Schedule",
            "schedule_type": "date",
            "start_month": 12,
            "start_day": 15,
            "end_month": 1,
            "end_day": 15,
            "uid": "winter-schedule",
        }
    }
    entry = _create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get calendar entity
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events spanning year boundary
    start = datetime(2023, 12, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 2, 29, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Winter Schedule"
    assert events[0].start == date(2023, 12, 15)
    assert events[0].end == date(2024, 1, 16)  # January 15 + 1 day


async def test_calendar_no_schedules(hass: HomeAssistant) -> None:
    """Test calendar entity with no schedules."""
    entry = _create_service_entry()  # Empty schedules
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the calendar entity
    state = hass.states.get("calendar.test_scheduler")
    assert state is not None

    # Get calendar entity
    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events for 2024
    start = datetime(2024, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 12, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 0


async def test_calendar_entity_attributes_no_active_event(
    hass: HomeAssistant, freezer
) -> None:
    """Test calendar entity attributes when no event is active."""
    # Set date to January 1, 2024 (outside any schedule)
    freezer.move_to("2024-01-01 12:00:00")

    schedules = {
        "summer-schedule": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "summer-schedule",
        }
    }

    default_config = {
        "summary": "Default Event",
        "location": "Home",
    }

    entry = _create_service_entry(schedules=schedules, configuration=default_config)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the calendar entity
    calendar_entity = None
    for entity in hass.data["calendar"].entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar_entity = entity
            break

    assert calendar_entity is not None

    # Check that no event is currently active
    current_event = calendar_entity.event
    assert current_event is None

    # Check extra state attributes when no event is active
    attrs = calendar_entity.extra_state_attributes
    assert attrs["name"] is None
    assert attrs["schedule_uid"] is None
    assert attrs["configuration"]["summary"] == "Default Event"
    assert attrs["default_configuration"]["summary"] == "Default Event"
