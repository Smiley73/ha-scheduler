"""Test edge cases for calendar functionality."""

from datetime import date, datetime

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.calendar import SchedulerCalendar
from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _create_calendar_from_entry(entry: MockConfigEntry) -> SchedulerCalendar:
    """Helper to create calendar with proper service data structure."""
    services = entry.options.get("services", {})
    service_id, service_data = next(iter(services.items()))
    return SchedulerCalendar(entry, service_id, service_data)


async def test_calendar_with_empty_schedules(hass: HomeAssistant) -> None:
    """Test calendar behavior with no schedules."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Empty Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Empty Scheduler",
                    "schedules": {},
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    # Should return None for current event
    assert calendar.event is None

    # Should return empty list for events
    events = await calendar.async_get_events(
        hass, datetime(2024, 1, 1), datetime(2024, 12, 31)
    )
    assert events == []


async def test_calendar_with_invalid_schedules(hass: HomeAssistant) -> None:
    """Test calendar behavior with invalid schedule data."""
    invalid_schedules = {
        "invalid_1": {
            "name": "Invalid Schedule 1",
            "schedule_type": "invalid_type",
            "uid": "invalid_1",
        }
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Invalid Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Invalid Scheduler",
                    "schedules": invalid_schedules,
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    # Should handle invalid schedules gracefully
    try:
        events = await calendar.async_get_events(
            hass, datetime(2024, 1, 1), datetime(2024, 12, 31)
        )
        # Should return empty list for invalid schedule types
        assert isinstance(events, list)
    except KeyError:
        # Expected if schedule has missing required fields
        pass


async def test_calendar_year_boundary_events(hass: HomeAssistant) -> None:
    """Test calendar events that cross year boundaries."""
    schedules = {
        "year_wrap": {
            "name": "Year Wrap Schedule",
            "schedule_type": "date",
            "start_month": 12,
            "start_day": 15,
            "end_month": 1,
            "end_day": 15,
            "uid": "year_wrap",
        }
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Year Wrap Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Year Wrap Scheduler",
                    "schedules": schedules,
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    # Request events across year boundary
    events = await calendar.async_get_events(
        hass, datetime(2023, 12, 1), datetime(2024, 2, 1)
    )

    # Should include the year-wrapping schedule
    assert len(events) >= 1

    # Find the year-wrap event
    year_wrap_events = [e for e in events if e.summary == "Year Wrap Schedule"]
    assert len(year_wrap_events) >= 1

    # Verify it spans the year boundary
    event = year_wrap_events[0]
    assert event.start.month == 12
    assert event.end.month == 1


async def test_calendar_leap_year_handling(hass: HomeAssistant) -> None:
    """Test calendar handles leap year dates correctly."""
    schedules = {
        "leap_day": {
            "name": "Leap Day Schedule",
            "schedule_type": "date",
            "start_month": 2,
            "start_day": 29,  # Feb 29
            "end_month": 3,
            "end_day": 1,
            "uid": "leap_day",
        }
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Leap Year Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Leap Year Scheduler",
                    "schedules": schedules,
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    # Test in leap year (2024)
    events_leap = await calendar.async_get_events(
        hass, datetime(2024, 2, 1), datetime(2024, 3, 31)
    )

    # Should have event starting Feb 29
    leap_events = [e for e in events_leap if e.summary == "Leap Day Schedule"]
    assert len(leap_events) == 1
    assert leap_events[0].start.month == 2
    assert leap_events[0].start.day == 29

    # Test in non-leap year (2023)
    events_non_leap = await calendar.async_get_events(
        hass, datetime(2023, 2, 1), datetime(2023, 3, 31)
    )

    # Should have event starting Feb 28 (clamped)
    non_leap_events = [e for e in events_non_leap if e.summary == "Leap Day Schedule"]
    assert len(non_leap_events) == 1
    assert non_leap_events[0].start.month == 2
    assert non_leap_events[0].start.day == 28


async def test_calendar_very_long_date_range(hass: HomeAssistant) -> None:
    """Test calendar with very long date range request."""
    schedules = {
        "annual": {
            "name": "Annual Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "annual",
        }
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Annual Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Annual Scheduler",
                    "schedules": schedules,
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    # Request 10 years of events
    events = await calendar.async_get_events(
        hass, datetime(2020, 1, 1), datetime(2030, 12, 31)
    )

    # Should have events for multiple years
    assert len(events) >= 10  # At least one per year

    # Verify events span multiple years
    years = {e.start.year for e in events}
    assert len(years) >= 10


async def test_calendar_current_event_selection(hass: HomeAssistant) -> None:
    """Test calendar current event selection logic."""
    from unittest.mock import patch

    schedules = {
        "current": {
            "name": "Current Schedule",
            "schedule_type": "date",
            "start_month": 1,
            "start_day": 1,
            "end_month": 12,
            "end_day": 31,
            "uid": "current",
        },
        "future": {
            "name": "Future Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "future",
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Current Event Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Current Event Scheduler",
                    "schedules": schedules,
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    # Mock current date to be within first schedule
    with patch("homeassistant.util.dt.now") as mock_now:
        mock_now.return_value.date.return_value = date(2024, 3, 15)

        current_event = calendar.event

        # Should return the current active schedule
        assert current_event is not None
        assert current_event.summary == "Current Schedule"


async def test_calendar_upcoming_event_selection_when_idle(
    hass: HomeAssistant,
) -> None:
    """Test calendar selects the next upcoming schedule when idle."""
    from unittest.mock import patch

    schedules = {
        "future": {
            "name": "Future Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "future",
        }
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Upcoming Event Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Upcoming Event Scheduler",
                    "schedules": schedules,
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    with patch("homeassistant.util.dt.now") as mock_now:
        mock_now.return_value.date.return_value = date(2024, 1, 15)

        current_event = calendar.event

        assert current_event is not None
        assert current_event.summary == "Future Schedule"
        assert current_event.start == date(2024, 6, 1)
        assert current_event.end == date(2024, 9, 1)


async def test_calendar_overlapping_schedules(hass: HomeAssistant) -> None:
    """Test calendar with overlapping schedules."""
    schedules = {
        "overlap_1": {
            "name": "Overlap Schedule 1",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "overlap_1",
        },
        "overlap_2": {
            "name": "Overlap Schedule 2",
            "schedule_type": "date",
            "start_month": 7,
            "start_day": 1,
            "end_month": 9,
            "end_day": 30,
            "uid": "overlap_2",
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Overlap Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Overlap Scheduler",
                    "schedules": schedules,
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    events = await calendar.async_get_events(
        hass, datetime(2024, 6, 1), datetime(2024, 9, 30)
    )

    # Should have both overlapping schedules
    assert len(events) == 2

    # Verify both schedules are present
    summaries = {e.summary for e in events}
    assert "Overlap Schedule 1" in summaries
    assert "Overlap Schedule 2" in summaries


async def test_calendar_configuration_inheritance(hass: HomeAssistant) -> None:
    """Test calendar configuration inheritance from default to schedule-specific."""
    default_config = {"default_setting": "default_value"}
    schedule_config = {"schedule_setting": "schedule_value"}

    schedules = {
        "with_config": {
            "name": "Schedule With Config",
            "schedule_type": "date",
            "start_month": 1,
            "start_day": 1,
            "end_month": 1,
            "end_day": 31,
            "uid": "with_config",
            "configuration": schedule_config,
        },
        "without_config": {
            "name": "Schedule Without Config",
            "schedule_type": "date",
            "start_month": 2,
            "start_day": 1,
            "end_month": 2,
            "end_day": 28,
            "uid": "without_config",
            # No configuration - should use default
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Config Test Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Config Test Scheduler",
                    "schedules": schedules,
                    "configuration": default_config,
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    events = await calendar.async_get_events(
        hass, datetime(2024, 1, 1), datetime(2024, 2, 29)
    )

    # Should have both events
    assert len(events) == 2

    # Verify descriptions are empty (configuration is now in attributes)
    for event in events:
        assert event.description == ""


async def test_calendar_update_listener(hass: HomeAssistant) -> None:
    """Test calendar update listener functionality."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Update Test Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Update Test Scheduler",
                    "schedules": {},
                    "configuration": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)
    # The listener is only registered once the entity is added to hass, at
    # which point entity.hass is always set; mirror that here.
    calendar.hass = hass

    # Mock the async_write_ha_state method
    from unittest.mock import Mock

    calendar.async_write_ha_state = Mock()

    # Trigger update listener
    await calendar._async_options_updated(hass, entry)

    # Verify state update was called
    calendar.async_write_ha_state.assert_called_once()


async def test_calendar_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test calendar extra state attributes."""
    default_config = {"test_setting": "test_value"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Attributes Test Scheduler",
        data={},
        options={
            "services": {
                "default": {
                    "name": "Attributes Test Scheduler",
                    "schedules": {},
                    "configuration": default_config,
                }
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    calendar = _create_calendar_from_entry(entry)

    attributes = calendar.extra_state_attributes

    assert "default_configuration" in attributes
    assert attributes["default_configuration"] == default_config
