"""Test schedule persistence through config entries."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_single_schedule_persists(hass: HomeAssistant) -> None:
    """Test that a single schedule is saved correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add a schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify via calendar entity that schedule exists
    from datetime import datetime

    from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
    from homeassistant.util import dt as dt_util

    calendar_entities = hass.data[CALENDAR_DOMAIN].entities
    calendar = None
    for entity in calendar_entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar = entity
            break

    assert calendar is not None

    # Request events for summer 2024
    start = datetime(2024, 6, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 8, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Test Schedule"


async def test_multiple_schedules_persist(hass: HomeAssistant) -> None:
    """Test that multiple schedules are saved without overwriting each other."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add first schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Winter Schedule",
            "start_month": "1",
            "start_day": 1,
            "end_month": "3",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Add second schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Summer Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify via calendar entity that both schedules exist
    from datetime import datetime

    from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
    from homeassistant.util import dt as dt_util

    calendar_entities = hass.data[CALENDAR_DOMAIN].entities
    calendar = None
    for entity in calendar_entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar = entity
            break

    assert calendar is not None

    # Request events for entire year 2024
    start = datetime(2024, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 12, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    # Should have both schedules
    assert len(events) == 2
    event_names = {event.summary for event in events}
    assert "Winter Schedule" in event_names
    assert "Summer Schedule" in event_names


async def test_three_schedules_persist(hass: HomeAssistant) -> None:
    """Test that three schedules can be added without issues."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    schedules_to_add = [
        ("Spring", "3", 1, "5", 31),
        ("Summer", "6", 1, "8", 31),
        ("Fall", "9", 1, "11", 30),
    ]

    for name, start_month, start_day, end_month, end_day in schedules_to_add:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_schedule"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"schedule_type": "date"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": name,
                "start_month": start_month,
                "start_day": start_day,
                "end_month": end_month,
                "end_day": end_day,
                "configuration": "",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify all three schedules exist
    from datetime import datetime

    from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
    from homeassistant.util import dt as dt_util

    calendar_entities = hass.data[CALENDAR_DOMAIN].entities
    calendar = None
    for entity in calendar_entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar = entity
            break

    assert calendar is not None

    # Request events for entire year 2024
    start = datetime(2024, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 12, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    # Should have all three schedules
    assert len(events) == 3
    event_names = {event.summary for event in events}
    assert event_names == {"Spring", "Summer", "Fall"}


async def test_schedule_with_configuration_persists(hass: HomeAssistant) -> None:
    """Test that schedule configuration is saved correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add schedule with configuration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Configured Schedule",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "mode: vacation\ntemp: 72",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify configuration is in event description
    from datetime import datetime

    from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
    from homeassistant.util import dt as dt_util

    calendar_entities = hass.data[CALENDAR_DOMAIN].entities
    calendar = None
    for entity in calendar_entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar = entity
            break

    assert calendar is not None

    start = datetime(2024, 6, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 8, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Configured Schedule"
    # Configuration should be a dict
    assert isinstance(events[0].description, dict)
    assert events[0].description.get("mode") == "vacation"
    assert events[0].description.get("temp") == 72


async def test_overlap_detection_works_across_adds(hass: HomeAssistant) -> None:
    """Test that overlap detection works when adding multiple schedules."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add first schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Schedule 1",
            "start_month": "3",
            "start_day": 1,
            "end_month": "6",
            "end_day": 30,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Try to add overlapping schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Schedule 2",
            "start_month": "5",  # Overlaps with Schedule 1
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )

    # Should show error
    assert result["type"] == FlowResultType.FORM
    assert "errors" in result
    assert "base" in result["errors"]
    assert "Schedule 1" in result["errors"]["base"]

    # Verify only one schedule exists
    from datetime import datetime

    from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
    from homeassistant.util import dt as dt_util

    calendar_entities = hass.data[CALENDAR_DOMAIN].entities
    calendar = None
    for entity in calendar_entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar = entity
            break

    assert calendar is not None

    start = datetime(2024, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 12, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    # Should only have the first schedule
    assert len(events) == 1
    assert events[0].summary == "Schedule 1"


async def test_different_schedule_types_persist(hass: HomeAssistant) -> None:
    """Test that different schedule types can coexist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add date schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "date"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Date Schedule",
            "start_month": "1",
            "start_day": 1,
            "end_month": "2",
            "end_day": 28,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Add week schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "week"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Week Schedule",
            "start_month": "6",
            "start_week": "0",
            "start_day_of_week": "0",
            "end_month": "6",
            "end_week": "4",
            "end_day_of_week": "4",
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Add nth-day schedule
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "nth-day"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Nth Day Schedule",
            "month": "9",
            "occurrence": "1",
            "day_of_week": "1",
            "start_offset": 0,
            "end_offset": 0,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify all three schedules exist
    from datetime import datetime

    from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
    from homeassistant.util import dt as dt_util

    calendar_entities = hass.data[CALENDAR_DOMAIN].entities
    calendar = None
    for entity in calendar_entities:
        if entity.entity_id == "calendar.test_scheduler":
            calendar = entity
            break

    assert calendar is not None

    start = datetime(2024, 1, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 12, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    # Should have all three schedules
    assert len(events) == 3
    event_names = {event.summary for event in events}
    assert event_names == {"Date Schedule", "Week Schedule", "Nth Day Schedule"}
