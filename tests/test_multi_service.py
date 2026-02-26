"""Test config entries with multiple services."""

from datetime import datetime

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _create_multi_service_entry() -> MockConfigEntry:
    """Create a config entry with two services (default + service-b)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Multi Service Scheduler",
        data={"scheduler_name": "Multi Service Scheduler"},
        options={
            "services": {
                "default": {
                    "name": "Service A",
                    "schedules": {
                        "summer": {
                            "uid": "summer",
                            "name": "Summer",
                            "schedule_type": "date",
                            "start_month": 6,
                            "start_day": 1,
                            "end_month": 8,
                            "end_day": 31,
                        }
                    },
                    "configuration": {"service": "A"},
                },
                "service-b": {
                    "name": "Service B",
                    "schedules": {
                        "winter": {
                            "uid": "winter",
                            "name": "Winter",
                            "schedule_type": "date",
                            "start_month": 12,
                            "start_day": 1,
                            "end_month": 2,
                            "end_day": 28,
                        }
                    },
                    "configuration": {"service": "B"},
                },
            }
        },
        version=2,
        minor_version=1,
    )


async def test_multi_service_creates_one_calendar_per_service(
    hass: HomeAssistant,
) -> None:
    """Test that a multi-service entry creates a calendar entity for each service."""
    entry = _create_multi_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state_a = hass.states.get("calendar.service_a")
    state_b = hass.states.get("calendar.service_b")

    assert state_a is not None, "calendar.service_a entity not found"
    assert state_b is not None, "calendar.service_b entity not found"


async def test_multi_service_each_calendar_shows_own_schedules(
    hass: HomeAssistant,
) -> None:
    """Test that each service's calendar shows only its own schedules."""
    entry = _create_multi_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cal_a = hass.data["calendar"].get_entity("calendar.service_a")
    cal_b = hass.data["calendar"].get_entity("calendar.service_b")

    assert cal_a is not None
    assert cal_b is not None

    # Both calendars queried for summer 2024
    start = datetime(2024, 6, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 8, 31, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    events_a = await cal_a.async_get_events(hass, start, end)
    events_b = await cal_b.async_get_events(hass, start, end)

    # Service A has the summer schedule; Service B has winter (not in this range)
    assert len(events_a) == 1
    assert events_a[0].summary == "Summer"

    assert len(events_b) == 0


async def test_multi_service_default_has_entry_id_as_unique_id(
    hass: HomeAssistant,
) -> None:
    """Test default service uses entry_id as unique_id; others append service_id."""
    entry = _create_multi_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cal_a = hass.data["calendar"].get_entity("calendar.service_a")
    cal_b = hass.data["calendar"].get_entity("calendar.service_b")

    # Default service: unique_id == entry_id
    assert cal_a.unique_id == entry.entry_id
    # Non-default service: unique_id == entry_id + "_" + service_id
    assert cal_b.unique_id == f"{entry.entry_id}_service-b"
    # They must differ
    assert cal_a.unique_id != cal_b.unique_id


async def test_multi_service_default_configuration_is_per_service(
    hass: HomeAssistant,
) -> None:
    """Test that each service reports its own default_configuration in state attributes."""
    entry = _create_multi_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cal_a = hass.data["calendar"].get_entity("calendar.service_a")
    cal_b = hass.data["calendar"].get_entity("calendar.service_b")

    attrs_a = cal_a.extra_state_attributes
    attrs_b = cal_b.extra_state_attributes

    assert attrs_a["default_configuration"]["service"] == "A"
    assert attrs_b["default_configuration"]["service"] == "B"
