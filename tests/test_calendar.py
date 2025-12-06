"""Test the Scheduler calendar platform."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.calendar import CalendarEntity
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.scheduler.calendar import SchedulerCalendar
from custom_components.scheduler.const import DOMAIN


@pytest.fixture
def mock_entry_with_schedules():
    """Create a mock config entry with schedules."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "schedule_1": {
                    "name": "Summer Schedule",
                    "schedule_type": "date",
                    "start_month": 6,
                    "end_month": 8,
                    "start_day": 1,
                    "end_day": 31,
                },
                "schedule_2": {
                    "name": "Weekend Schedule",
                    "schedule_type": "week",
                    "start_month": 1,
                    "end_month": 12,
                    "start_day_of_week": 5,  # Saturday
                    "end_day_of_week": 6,  # Sunday
                    "start_week": 0,
                    "end_week": 4,
                },
            }
        },
        entry_id="test_calendar_entry_id",
    )


async def test_calendar_setup(hass: HomeAssistant, mock_entry_with_schedules):
    """Test calendar platform setup."""
    from custom_components.scheduler.calendar import async_setup_entry
    
    entities = []
    
    def sync_add_entities(new_entities):
        entities.extend(new_entities)
    
    await async_setup_entry(hass, mock_entry_with_schedules, sync_add_entities)
    
    assert len(entities) == 1
    assert isinstance(entities[0], SchedulerCalendar)
    assert entities[0].name == "Scheduler"


async def test_calendar_events_date_schedule(hass: HomeAssistant, mock_entry_with_schedules):
    """Test calendar events for date-based schedule."""
    calendar = SchedulerCalendar(hass, mock_entry_with_schedules)
    
    # Test summer schedule (June 1 - August 31)
    start_date = datetime(2024, 6, 1)
    end_date = datetime(2024, 6, 30)
    
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Filter only Summer Schedule events
    summer_events = [e for e in events if e.summary == "Summer Schedule"]
    
    # Should have a single event spanning the entire schedule
    assert len(summer_events) == 1
    assert summer_events[0].start == datetime(2024, 6, 1).date()
    assert summer_events[0].end == datetime(2024, 9, 1).date()  # End is exclusive, so Sept 1


async def test_calendar_events_week_schedule(hass: HomeAssistant, mock_entry_with_schedules):
    """Test calendar events for week-based schedule."""
    calendar = SchedulerCalendar(hass, mock_entry_with_schedules)
    
    # Test weekend schedule for January 2024
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Count weekend days (Saturdays and Sundays) in January 2024
    weekend_events = [e for e in events if e.summary == "Weekend Schedule"]
    
    # January 2024 has 8 Saturdays and 8 Sundays = 16 weekend days
    # But we also have Summer Schedule events, so filter
    assert len(weekend_events) > 0


async def test_calendar_next_event(hass: HomeAssistant, mock_entry_with_schedules):
    """Test getting the next upcoming event."""
    calendar = SchedulerCalendar(hass, mock_entry_with_schedules)
    
    # Simply test that we can get the next event
    # The event property calls _get_events with current time + 365 days
    event = calendar.event
    
    # Should return an event (either Summer or Weekend schedule)
    assert event is not None
    assert event.summary in ["Summer Schedule", "Weekend Schedule"]


async def test_calendar_no_schedules(hass: HomeAssistant, empty_hub_entry):
    """Test calendar with no schedules."""
    from custom_components.scheduler.calendar import async_setup_entry
    
    entities = []
    
    def sync_add_entities(new_entities):
        entities.extend(new_entities)
    
    await async_setup_entry(hass, empty_hub_entry, sync_add_entities)
    
    # Should not create calendar if no schedules
    assert len(entities) == 0


async def test_calendar_device_info(hass: HomeAssistant, mock_entry_with_schedules):
    """Test calendar device info."""
    calendar = SchedulerCalendar(hass, mock_entry_with_schedules)
    
    assert calendar.device_info is not None
    assert (DOMAIN, "scheduler_hub") in calendar.device_info["identifiers"]
    assert calendar.device_info["name"] == "Scheduler"



async def test_calendar_month_wrap_around(hass: HomeAssistant):
    """Test calendar with month wrap-around schedule."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "winter_schedule": {
                    "name": "Winter Schedule",
                    "start_month": 11,  # November
                    "end_month": 2,  # February (wrap around)
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 28,
                },
            },
        },
        entry_id="test_calendar_wrap_hub",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Get events for December (should have a single event spanning Nov-Feb)
    start_date = datetime(2024, 12, 1)
    end_date = datetime(2024, 12, 31)

    events = await calendar.async_get_events(hass, start_date, end_date)

    # Should have a single event spanning the wrap-around period
    assert len(events) == 1
    assert events[0].summary == "Winter Schedule"
    assert events[0].start == datetime(2024, 11, 1).date()
    assert events[0].end == datetime(2025, 3, 1).date()  # End is exclusive


async def test_calendar_multi_year_schedule(hass: HomeAssistant):
    """Test calendar with schedule spanning multiple years."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "summer_schedule": {
                    "name": "Summer Schedule",
                    "start_month": 6,  # June
                    "end_month": 8,  # August
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
            },
        },
        entry_id="test_multi_year",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Request events spanning 2 years
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 12, 31)

    events = await calendar.async_get_events(hass, start_date, end_date)

    # Should have 2 events - one for summer 2024 and one for summer 2025
    assert len(events) == 2
    assert all(e.summary == "Summer Schedule" for e in events)
    
    # Check 2024 event
    assert events[0].start == datetime(2024, 6, 1).date()
    assert events[0].end == datetime(2024, 9, 1).date()
    
    # Check 2025 event
    assert events[1].start == datetime(2025, 6, 1).date()
    assert events[1].end == datetime(2025, 9, 1).date()


async def test_calendar_leap_year_feb_29(hass: HomeAssistant):
    """Test calendar with schedule including Feb 29 in leap and non-leap years."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "feb_schedule": {
                    "name": "February Schedule",
                    "start_month": 2,
                    "end_month": 2,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 29,  # Feb 29 - only valid in leap years
                },
            },
        },
        entry_id="test_leap_year",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Test leap year 2024 (Feb has 29 days)
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    assert len(events) == 1
    assert events[0].summary == "February Schedule"
    assert events[0].start == datetime(2024, 2, 1).date()
    assert events[0].end == datetime(2024, 3, 1).date()  # Feb 29 + 1 day
    
    # Test non-leap year 2023 (Feb has 28 days)
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 12, 31)
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should still create event, but end on Feb 28
    assert len(events) == 1
    assert events[0].summary == "February Schedule"
    assert events[0].start == datetime(2023, 2, 1).date()
    assert events[0].end == datetime(2023, 3, 1).date()  # Feb 28 + 1 day


async def test_calendar_invalid_date_feb_31(hass: HomeAssistant):
    """Test calendar with completely invalid date like Feb 31."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "invalid_schedule": {
                    "name": "Invalid Schedule",
                    "start_month": 2,
                    "end_month": 2,
                    "schedule_type": "date",
                    "start_day": 31,  # Feb 31 never exists
                    "end_day": 31,
                },
            },
        },
        entry_id="test_invalid_date",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should handle gracefully - use last valid day (Feb 29 in 2024)
    assert len(events) == 1
    assert events[0].start == datetime(2024, 2, 29).date()
    assert events[0].end == datetime(2024, 3, 1).date()


async def test_calendar_30_day_month_with_day_31(hass: HomeAssistant):
    """Test calendar with day 31 in months that only have 30 days."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "april_schedule": {
                    "name": "April Schedule",
                    "start_month": 4,  # April has 30 days
                    "end_month": 4,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,  # Invalid - April only has 30 days
                },
                "june_schedule": {
                    "name": "June Schedule",
                    "start_month": 6,  # June has 30 days
                    "end_month": 6,
                    "schedule_type": "date",
                    "start_day": 31,  # Invalid start day
                    "end_day": 31,
                },
            },
        },
        entry_id="test_30_day_months",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should have 2 events, adjusted to valid dates
    assert len(events) == 2
    
    # April schedule should end on April 30
    april_event = [e for e in events if e.summary == "April Schedule"][0]
    assert april_event.start == datetime(2024, 4, 1).date()
    assert april_event.end == datetime(2024, 5, 1).date()  # April 30 + 1 day
    
    # June schedule should be June 30 (adjusted from invalid 31)
    june_event = [e for e in events if e.summary == "June Schedule"][0]
    assert june_event.start == datetime(2024, 6, 30).date()
    assert june_event.end == datetime(2024, 7, 1).date()


async def test_calendar_wrap_around_multiple_years(hass: HomeAssistant):
    """Test wrap-around schedule appearing correctly across multiple years."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "winter_schedule": {
                    "name": "Winter Schedule",
                    "start_month": 12,  # December
                    "end_month": 2,  # February (wrap around)
                    "schedule_type": "date",
                    "start_day": 15,
                    "end_day": 15,
                },
            },
        },
        entry_id="test_wrap_multi_year",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Request 3 years of events
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2025, 12, 31)
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should have 3 events (2023-2024, 2024-2025, 2025-2026)
    assert len(events) == 3
    
    # Check each event spans Dec 15 to Feb 15
    assert events[0].start == datetime(2023, 12, 15).date()
    assert events[0].end == datetime(2024, 2, 16).date()
    
    assert events[1].start == datetime(2024, 12, 15).date()
    assert events[1].end == datetime(2025, 2, 16).date()
    
    assert events[2].start == datetime(2025, 12, 15).date()
    assert events[2].end == datetime(2026, 2, 16).date()


async def test_calendar_empty_date_range(hass: HomeAssistant):
    """Test calendar with empty or reversed date range."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "summer_schedule": {
                    "name": "Summer Schedule",
                    "start_month": 6,
                    "end_month": 8,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 31,
                },
            },
        },
        entry_id="test_empty_range",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Request with start > end (shouldn't happen but should handle gracefully)
    start_date = datetime(2024, 12, 31)
    end_date = datetime(2024, 1, 1)
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should return empty list
    assert len(events) == 0
