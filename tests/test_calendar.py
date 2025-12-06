"""Test the Scheduler calendar platform."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.calendar import CalendarEntity
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
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
    # With translations, name is None and derived from translation_key
    assert entities[0].translation_key == "scheduler"
    assert entities[0].has_entity_name is True


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
    assert summer_events[0].start == dt_util.start_of_local_day(datetime(2024, 6, 1))
    # End should be 23:59:59 on August 31
    expected_end = dt_util.as_local(datetime(2024, 8, 31, 23, 59, 59))
    assert summer_events[0].end == expected_end


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
    assert events[0].start == dt_util.start_of_local_day(datetime(2024, 11, 1))
    # End should be 23:59:59 on February 28
    expected_end = dt_util.as_local(datetime(2025, 2, 28, 23, 59, 59))
    assert events[0].end == expected_end


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
    assert events[0].start == dt_util.start_of_local_day(datetime(2024, 6, 1))
    assert events[0].end == dt_util.as_local(datetime(2024, 8, 31, 23, 59, 59))
    
    # Check 2025 event
    assert events[1].start == dt_util.start_of_local_day(datetime(2025, 6, 1))
    assert events[1].end == dt_util.as_local(datetime(2025, 8, 31, 23, 59, 59))


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
    assert events[0].start == dt_util.start_of_local_day(datetime(2024, 2, 1))
    assert events[0].end == dt_util.as_local(datetime(2024, 2, 29, 23, 59, 59))
    
    # Test non-leap year 2023 (Feb has 28 days)
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 12, 31)
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should still create event, but end on Feb 28
    assert len(events) == 1
    assert events[0].summary == "February Schedule"
    assert events[0].start == dt_util.start_of_local_day(datetime(2023, 2, 1))
    assert events[0].end == dt_util.as_local(datetime(2023, 2, 28, 23, 59, 59))


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
    assert events[0].start == dt_util.start_of_local_day(datetime(2024, 2, 29))
    assert events[0].end == dt_util.as_local(datetime(2024, 2, 29, 23, 59, 59))


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
    assert april_event.start == dt_util.start_of_local_day(datetime(2024, 4, 1))
    assert april_event.end == dt_util.as_local(datetime(2024, 4, 30, 23, 59, 59))
    
    # June schedule should be June 30 (adjusted from invalid 31)
    june_event = [e for e in events if e.summary == "June Schedule"][0]
    assert june_event.start == dt_util.start_of_local_day(datetime(2024, 6, 30))
    assert june_event.end == dt_util.as_local(datetime(2024, 6, 30, 23, 59, 59))


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
    assert events[0].start == dt_util.start_of_local_day(datetime(2023, 12, 15))
    assert events[0].end == dt_util.as_local(datetime(2024, 2, 15, 23, 59, 59))
    
    assert events[1].start == dt_util.start_of_local_day(datetime(2024, 12, 15))
    assert events[1].end == dt_util.as_local(datetime(2025, 2, 15, 23, 59, 59))
    
    assert events[2].start == dt_util.start_of_local_day(datetime(2025, 12, 15))
    assert events[2].end == dt_util.as_local(datetime(2026, 2, 15, 23, 59, 59))


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



async def test_calendar_week_schedule_dow_boundaries(hass: HomeAssistant):
    """Test that week-based schedules respect day-of-week boundaries."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "weekday_schedule": {
                    "name": "Weekday Schedule",
                    "schedule_type": "week",
                    "start_month": 5,  # May only
                    "end_month": 5,
                    "start_day_of_week": 0,  # Monday
                    "end_day_of_week": 4,  # Friday
                    "start_week": 1,  # 2nd week (0-indexed)
                    "end_week": 3,  # 4th week (0-indexed)
                },
            },
        },
        entry_id="test_dow_boundaries",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Test May 2026
    start_date = datetime(2026, 5, 1)
    end_date = datetime(2026, 5, 31)
    
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should have exactly 1 event
    assert len(events) == 1
    
    event = events[0]
    assert event.summary == "Weekday Schedule"
    
    # Event should start on a Monday (weekday 0)
    assert event.start.weekday() == 0, f"Should start on Monday, got {event.start.strftime('%A')}"
    
    # Event should end on a Friday (weekday 4)
    assert event.end.weekday() == 4, f"Should end on Friday, got {event.end.strftime('%A')}"
    
    # Verify specific dates for May 2026
    # Week 1 (days 8-14): First Monday is May 11
    # Week 3 (days 22-28): Last Friday is May 22
    assert event.start == dt_util.start_of_local_day(datetime(2026, 5, 11))
    assert event.end == dt_util.as_local(datetime(2026, 5, 22, 23, 59, 59))


async def test_calendar_week_schedule_weekend_boundaries(hass: HomeAssistant):
    """Test week-based schedule with Saturday-Sunday boundaries."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "weekend_schedule": {
                    "name": "Weekend Schedule",
                    "schedule_type": "week",
                    "start_month": 6,  # June only
                    "end_month": 6,
                    "start_day_of_week": 5,  # Saturday
                    "end_day_of_week": 6,  # Sunday
                    "start_week": 0,  # All weeks
                    "end_week": 4,
                },
            },
        },
        entry_id="test_weekend_boundaries",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Test June 2024
    start_date = datetime(2024, 6, 1)
    end_date = datetime(2024, 6, 30)
    
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should have exactly 1 event spanning all weekends
    assert len(events) == 1
    
    event = events[0]
    assert event.summary == "Weekend Schedule"
    
    # Event should start on a Saturday (weekday 5)
    assert event.start.weekday() == 5, f"Should start on Saturday, got {event.start.strftime('%A')}"
    
    # Event should end on a Sunday (weekday 6)
    assert event.end.weekday() == 6, f"Should end on Sunday, got {event.end.strftime('%A')}"
    
    # June 2024: First Saturday is June 1, last Sunday is June 30
    assert event.start == dt_util.start_of_local_day(datetime(2024, 6, 1))
    assert event.end == dt_util.as_local(datetime(2024, 6, 30, 23, 59, 59))


async def test_calendar_week_schedule_single_day(hass: HomeAssistant):
    """Test week-based schedule with same start and end day of week."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "friday_schedule": {
                    "name": "Friday Only",
                    "schedule_type": "week",
                    "start_month": 1,
                    "end_month": 12,
                    "start_day_of_week": 4,  # Friday
                    "end_day_of_week": 4,  # Friday (same day)
                    "start_week": 0,
                    "end_week": 4,
                },
            },
        },
        entry_id="test_single_day",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Test January 2024
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should have exactly 1 event
    assert len(events) == 1
    
    event = events[0]
    
    # Both start and end should be Friday
    assert event.start.weekday() == 4
    assert event.end.weekday() == 4
    
    # January 2024: First Friday is Jan 5, last Friday is Jan 26
    assert event.start == dt_util.start_of_local_day(datetime(2024, 1, 5))
    assert event.end == dt_util.as_local(datetime(2024, 1, 26, 23, 59, 59))


async def test_calendar_week_schedule_multi_year_dow_boundaries(hass: HomeAssistant):
    """Test week-based schedule maintains day-of-week boundaries across years."""
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "weekday_schedule": {
                    "name": "Weekdays",
                    "schedule_type": "week",
                    "start_month": 1,
                    "end_month": 12,
                    "start_day_of_week": 0,  # Monday
                    "end_day_of_week": 4,  # Friday
                    "start_week": 0,
                    "end_week": 4,
                },
            },
        },
        entry_id="test_multi_year_dow",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Test across 2 years
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 12, 31)
    
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should have 2 events (one per year)
    assert len(events) == 2
    
    # Check 2024 event
    event_2024 = events[0]
    assert event_2024.start.year == 2024
    assert event_2024.start.weekday() == 0, "2024 event should start on Monday"
    assert event_2024.end.weekday() == 4, "2024 event should end on Friday"
    
    # Check 2025 event
    event_2025 = events[1]
    assert event_2025.start.year == 2025
    assert event_2025.start.weekday() == 0, "2025 event should start on Monday"
    assert event_2025.end.weekday() == 4, "2025 event should end on Friday"



async def test_calendar_week_schedule_all_days_active(hass: HomeAssistant):
    """Test that week-based schedules activate ALL days between start and end dates.
    
    This test verifies that day-of-week selection only determines the start/end dates,
    not which specific days are active. All days between start and end should be active.
    """
    # December schedule: weeks 0-3, Monday (start) to Wednesday (end)
    # Expected: Active from first Monday (Dec 2) to last Wednesday (Dec 25)
    # ALL days in between should be active, including weekends
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "december_schedule": {
                    "name": "December Schedule",
                    "schedule_type": "week",
                    "start_month": 12,
                    "end_month": 12,
                    "start_day_of_week": 0,  # Monday (determines start date)
                    "end_day_of_week": 2,  # Wednesday (determines end date)
                    "start_week": 0,
                    "end_week": 3,
                },
            }
        },
        entry_id="test_december",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Test December 2024
    start_date = datetime(2024, 12, 1)
    end_date = datetime(2024, 12, 31)
    
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should have exactly 1 event
    assert len(events) == 1
    
    event = events[0]
    assert event.summary == "December Schedule"
    
    # December 2024: Week 0 is days 1-7
    # First Monday is Dec 2, last Wednesday of week 3 (days 22-28) is Dec 25
    assert event.start == dt_util.start_of_local_day(datetime(2024, 12, 2))
    assert event.end == dt_util.as_local(datetime(2024, 12, 25, 23, 59, 59))
    
    # Verify the event spans from Monday to Wednesday but includes ALL days
    # Start should be Monday
    assert event.start.weekday() == 0, "Should start on Monday"
    # End should be Wednesday
    assert event.end.weekday() == 2, "Should end on Wednesday"
    
    # The period is 24 days (Dec 2-25), which includes weekends
    duration_days = (event.end.date() - event.start.date()).days + 1
    assert duration_days == 24, f"Expected 24 days, got {duration_days}"


async def test_calendar_week_schedule_includes_weekends(hass: HomeAssistant):
    """Test that weekends are included when they fall within the week-based range."""
    # Schedule: First 2 weeks, Monday to Friday
    # Expected: Active from first Monday to last Friday, INCLUDING the weekend in between
    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "two_weeks": {
                    "name": "Two Weeks",
                    "schedule_type": "week",
                    "start_month": 1,
                    "end_month": 1,
                    "start_day_of_week": 0,  # Monday
                    "end_day_of_week": 4,  # Friday
                    "start_week": 0,
                    "end_week": 1,
                },
            }
        },
        entry_id="test_two_weeks",
    )

    calendar = SchedulerCalendar(hass, hub_entry)
    
    # Test January 2024
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    
    events = await calendar.async_get_events(hass, start_date, end_date)
    
    # Should have exactly 1 event
    assert len(events) == 1
    
    event = events[0]
    
    # January 2024: Week 0 is days 1-7, Week 1 is days 8-14
    # First Monday is Jan 1, last Friday of week 1 is Jan 12
    assert event.start == dt_util.start_of_local_day(datetime(2024, 1, 1))
    assert event.end == dt_util.as_local(datetime(2024, 1, 12, 23, 59, 59))
    
    # The period is 12 days (Jan 1-12), which includes the weekend Jan 6-7
    duration_days = (event.end.date() - event.start.date()).days + 1
    assert duration_days == 12, f"Expected 12 days including weekend, got {duration_days}"
