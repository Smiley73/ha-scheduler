"""Test the Scheduler calendar."""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.ha_scheduler.const import CALENDAR_YEAR_LOOKAROUND

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_calendar_with_date_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedules)
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


async def test_calendar_with_week_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedules)
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


async def test_calendar_with_nth_day_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedules)
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


async def test_calendar_with_holiday_schedule(
    hass: HomeAssistant, create_service_entry, freezer
) -> None:
    """Test calendar entity with a holiday-backed schedule."""
    freezer.move_to("2026-04-03 12:00:00")

    schedules = {
        "test-schedule-1": {
            "name": "Good Friday",
            "schedule_type": "holiday",
            "country_code": "DE",
            "category": "public",
            "holiday_name": "Good Friday",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
            "uid": "test-schedule-1",
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    current_event = calendar.event
    assert current_event is not None
    assert current_event.summary == "Good Friday"
    assert current_event.start == date(2026, 4, 3)
    assert current_event.end == date(2026, 4, 4)

    attrs = calendar.extra_state_attributes
    assert attrs["name"] == "Good Friday"
    assert attrs["schedule_uid"] == "test-schedule-1"

    start = datetime(2026, 4, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2026, 4, 5, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Good Friday"
    assert events[0].start == date(2026, 4, 3)
    assert events[0].end == date(2026, 4, 4)


async def test_calendar_setup_primes_holiday_cache(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test calendar setup primes holiday caches off the event loop."""
    schedules = {
        "test-schedule-1": {
            "name": "Good Friday",
            "schedule_type": "holiday",
            "country_code": "DE",
            "category": "public",
            "holiday_name": "Good Friday",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
            "uid": "test-schedule-1",
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_scheduler.calendar.async_prime_holiday_cache",
        new=AsyncMock(),
    ) as mock_prime_holiday_cache:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_prime_holiday_cache.assert_awaited()


async def test_calendar_with_configuration(
    hass: HomeAssistant, create_service_entry, freezer
) -> None:
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
    entry = create_service_entry(schedules=schedules)
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


async def test_calendar_multiple_schedules(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedules)
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
    hass: HomeAssistant, create_service_entry, freezer
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

    entry = create_service_entry(schedules=schedules, configuration=default_config)
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


async def test_calendar_year_wrapping_schedule(
    hass: HomeAssistant, create_service_entry
) -> None:
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
    entry = create_service_entry(schedules=schedules)
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


async def test_calendar_no_schedules(hass: HomeAssistant, create_service_entry) -> None:
    """Test calendar entity with no schedules."""
    entry = create_service_entry()  # Empty schedules
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
    hass: HomeAssistant, create_service_entry, freezer
) -> None:
    """Test calendar entity attributes when the next event is upcoming."""
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

    entry = create_service_entry(schedules=schedules, configuration=default_config)
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

    # Check that the next event is surfaced even while idle.
    current_event = calendar_entity.event
    assert current_event is not None
    assert current_event.summary == "Summer Schedule"
    assert current_event.start == date(2024, 6, 1)
    assert current_event.end == date(2024, 9, 1)

    # Check extra state attributes follow the next upcoming schedule.
    attrs = calendar_entity.extra_state_attributes
    assert attrs["name"] == "Summer Schedule"
    assert attrs["schedule_uid"] == "summer-schedule"
    assert attrs["configuration"]["summary"] == "Default Event"
    assert attrs["default_configuration"]["summary"] == "Default Event"


def test_calendar_year_lookaround_constant() -> None:
    """Verify CALENDAR_YEAR_LOOKAROUND is set to 3 for a ±3-year event window."""
    assert CALENDAR_YEAR_LOOKAROUND == 3


async def test_calendar_event_window_spans_lookaround_years(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Test async_get_events returns exactly 2*CALENDAR_YEAR_LOOKAROUND+1 annual events."""
    today = date.today()
    current_year = today.year

    schedules = {
        "annual": {
            "name": "Annual Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 6,
            "end_day": 30,
            "uid": "annual",
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # Request events across the full ±CALENDAR_YEAR_LOOKAROUND window
    start = datetime(
        current_year - CALENDAR_YEAR_LOOKAROUND, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE
    )
    end = datetime(
        current_year + CALENDAR_YEAR_LOOKAROUND,
        12,
        31,
        tzinfo=dt_util.DEFAULT_TIME_ZONE,
    )

    events = await calendar.async_get_events(hass, start, end)

    # One event per year for 2*CALENDAR_YEAR_LOOKAROUND+1 years (7 total with default of 3)
    expected_count = CALENDAR_YEAR_LOOKAROUND * 2 + 1
    assert len(events) == expected_count

    event_years = {e.start.year for e in events}
    expected_years = set(
        range(
            current_year - CALENDAR_YEAR_LOOKAROUND,
            current_year + CALENDAR_YEAR_LOOKAROUND + 1,
        )
    )
    assert event_years == expected_years


async def test_configuration_attributes_excluded_from_recorder() -> None:
    """Configuration blobs must not be written to the recorder database.

    They are free-form user YAML (potentially large or sensitive); the
    recorder exclusion keeps them out of history while leaving them visible
    as live state attributes.
    """
    from custom_components.ha_scheduler.calendar import SchedulerCalendar

    assert "configuration" in SchedulerCalendar._unrecorded_attributes
    assert "default_configuration" in SchedulerCalendar._unrecorded_attributes
    # The Entity machinery folds _unrecorded_attributes into a combined
    # frozenset at class-creation time; verify the fold actually happened.
    combined = SchedulerCalendar._Entity__combined_unrecorded_attributes
    assert {"configuration", "default_configuration"} <= combined


async def test_multi_occurrence_holiday_events_have_unique_uids(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Each generated range must carry its own uid.

    Regression test: uids were keyed on the generation year, so a holiday
    occurring twice in one year produced two events with identical uids,
    breaking client-side dedup over the calendar APIs.
    """
    entry = create_service_entry(
        schedules={
            "eid": {
                "uid": "eid",
                "name": "Eid al-Fitr",
                "schedule_type": "holiday",
                "country_code": "AE",
                "category": "public",
                "holiday_name": "Eid al-Fitr",
                "name_lookup": "iexact",
                "start_offset": 0,
                "end_offset": 0,
            }
        }
    )
    entry.add_to_hass(hass)

    def _dates_for_year(country, category, name, lookup, year):
        # The real holidays library is year-scoped; only 2033 has the
        # double occurrence in this scenario.
        if year == 2033:
            return (date(2033, 1, 2), date(2033, 12, 23))
        return ()

    with patch(
        "custom_components.ha_scheduler.holiday_importer._get_named_holiday_dates_sync",
        side_effect=_dates_for_year,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("calendar.test_scheduler")
        assert state is not None

        calendar = next(
            e
            for e in hass.data["calendar"].entities
            if e.entity_id == "calendar.test_scheduler"
        )
        start = datetime(2033, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
        end = datetime(2033, 12, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)
        events = await calendar.async_get_events(hass, start, end)

    matching = [e for e in events if e.summary == "Eid al-Fitr"]
    assert len(matching) == 2
    uids = {e.uid for e in matching}
    assert len(uids) == 2, f"duplicate uids: {uids}"


async def test_calendar_does_not_poll_and_memoizes_event(
    hass: HomeAssistant, create_service_entry
) -> None:
    """The entity must not poll, and must compute the event once per write.

    All events are all-day: state can only change at local midnight (covered
    by the daily refresh and the calendar component's transition timers) or
    on options updates. The event/extra_state_attributes properties share one
    memoized computation instead of iterating all schedules twice.
    """
    from unittest.mock import patch as mock_patch

    entry = create_service_entry(
        schedules={
            "summer": {
                "uid": "summer",
                "name": "Summer",
                "schedule_type": "date",
                "start_month": 6,
                "start_day": 1,
                "end_month": 8,
                "end_day": 31,
            }
        }
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calendar = next(
        e
        for e in hass.data["calendar"].entities
        if e.entity_id == "calendar.test_scheduler"
    )

    assert calendar.should_poll is False

    calendar._event_cache = None
    with mock_patch.object(
        type(calendar),
        "_compute_current_or_upcoming_event",
        wraps=calendar._compute_current_or_upcoming_event,
    ) as mock_compute:
        _ = calendar.event
        _ = calendar.extra_state_attributes
        _ = calendar.event

    assert mock_compute.call_count == 1


async def test_get_events_end_bound_is_exclusive(
    hass: HomeAssistant, create_service_entry
) -> None:
    """end_date is an exclusive bound against the event start.

    Regression test: the overlap check used to truncate the bound to a date
    and compare inclusively, so a "July" query (end = Aug 1 00:00) also
    returned events starting exactly on Aug 1.
    """
    entry = create_service_entry(
        schedules={
            "aug": {
                "uid": "aug",
                "name": "August Schedule",
                "schedule_type": "date",
                "start_month": 8,
                "start_day": 1,
                "end_month": 8,
                "end_day": 5,
            }
        }
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")

    # "Events in July": end bound is exclusive, Aug 1 event must not appear.
    events = await calendar.async_get_events(
        hass,
        datetime(2026, 7, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE),
        datetime(2026, 8, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE),
    )
    assert events == []

    # Extending the bound past the event start includes it.
    events = await calendar.async_get_events(
        hass,
        datetime(2026, 7, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE),
        datetime(2026, 8, 2, tzinfo=dt_util.DEFAULT_TIME_ZONE),
    )
    assert len(events) == 1
    assert events[0].start == date(2026, 8, 1)

    # start_date is exclusive against the event end: a query starting exactly
    # at the event's (exclusive) end must not return it.
    events = await calendar.async_get_events(
        hass,
        datetime(2026, 8, 6, tzinfo=dt_util.DEFAULT_TIME_ZONE),
        datetime(2026, 9, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE),
    )
    assert events == []
