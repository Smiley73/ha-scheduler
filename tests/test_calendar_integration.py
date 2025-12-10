"""Test the Scheduler calendar integration with config flow."""

from datetime import datetime

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_calendar_updates_when_schedule_added(hass: HomeAssistant) -> None:
    """Test that calendar updates when a schedule is added via options flow."""
    # Create entry with no schedules
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify calendar exists but has no events
    state = hass.states.get("calendar.test_scheduler")
    assert state is not None

    # Get calendar entity
    from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN

    calendar_entities = hass.data[CALENDAR_DOMAIN].entities
    calendar = None
    for entity in calendar_entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar = entity
            break

    assert calendar is not None

    # Request events - should be empty
    start = datetime(2024, 6, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 6, 30, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)
    assert len(events) == 0

    # Now add a schedule via options update
    hass.config_entries.async_update_entry(
        entry,
        options={
            "schedules": {
                "test-schedule-1": {
                    "name": "Summer Schedule",
                    "schedule_type": "date",
                    "start_month": 6,
                    "start_day": 1,
                    "end_month": 6,
                    "end_day": 30,
                    "uid": "test-schedule-1",
                }
            }
        },
    )
    await hass.async_block_till_done()

    # Request events again - should now have the schedule
    events = await calendar.async_get_events(hass, start, end)
    assert len(events) == 1
    assert events[0].summary == "Summer Schedule"


async def test_calendar_shows_current_event(hass: HomeAssistant) -> None:
    """Test that calendar shows current event property."""
    # Create entry with a schedule that includes today
    from datetime import date

    today = date.today()

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "schedules": {
                "test-schedule-1": {
                    "name": "Current Schedule",
                    "schedule_type": "date",
                    "start_month": today.month,
                    "start_day": 1,
                    "end_month": today.month,
                    "end_day": 28,  # Safe for all months
                    "uid": "test-schedule-1",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get calendar entity
    from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN

    calendar_entities = hass.data[CALENDAR_DOMAIN].entities
    calendar = None
    for entity in calendar_entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar = entity
            break

    assert calendar is not None

    # Check current event
    current_event = calendar.event
    if today.day <= 28:
        # We're within the schedule
        assert current_event is not None
        assert current_event.summary == "Current Schedule"
    else:
        # We're outside the schedule
        assert current_event is None
