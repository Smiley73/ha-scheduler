"""Tests that one broken schedule cannot blank the whole calendar.

The holidays library raises NotImplementedError for unknown countries and
ValueError for categories it no longer supports — both can legitimately end up
in stored options when the installed holidays version changes underneath an
existing config entry. The calendar must keep serving the remaining schedules.
"""

import re
from datetime import date, datetime

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.ha_scheduler.holiday_importer import _clear_holiday_caches

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture(autouse=True)
def clear_holiday_caches():
    """Reset holiday resolver caches between tests.

    The resolver warns once per cached lookup; without a reset, a lookup cached
    by an earlier test would suppress the warning a later test asserts on.
    """
    _clear_holiday_caches()
    yield
    _clear_holiday_caches()


BROKEN_HOLIDAY_SCHEDULES = {
    "unknown-country": {
        "name": "Unknown Country Holiday",
        "schedule_type": "holiday",
        "country_code": "XX",
        "category": "public",
        "holiday_name": "Some Holiday",
        "name_lookup": "iexact",
        "start_offset": 0,
        "end_offset": 0,
        "uid": "unknown-country",
    },
    "unsupported-category": {
        "name": "Unsupported Category Holiday",
        "schedule_type": "holiday",
        "country_code": "US",
        "category": "bank",
        "holiday_name": "Christmas Day",
        "name_lookup": "iexact",
        "start_offset": 0,
        "end_offset": 0,
        "uid": "unsupported-category",
    },
}


@pytest.mark.parametrize("broken_id", list(BROKEN_HOLIDAY_SCHEDULES))
async def test_broken_holiday_schedule_does_not_blank_calendar(
    hass: HomeAssistant, create_service_entry, broken_id: str
) -> None:
    """A holiday schedule the library rejects must not hide other schedules."""
    schedules = {
        "date-schedule": {
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
            "uid": "date-schedule",
        },
        broken_id: BROKEN_HOLIDAY_SCHEDULES[broken_id],
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.test_scheduler")
    assert state is not None
    assert state.state != "unavailable"

    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")
    start = datetime(2024, 5, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 9, 30, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Summer Schedule"
    assert events[0].start == date(2024, 6, 1)


async def test_broken_holiday_schedule_logs_warning(
    hass: HomeAssistant,
    create_service_entry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rejected holiday providers surface as warnings, not silent debug noise."""
    entry = create_service_entry(
        schedules={"unknown-country": BROKEN_HOLIDAY_SCHEDULES["unknown-country"]}
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert any(
        record.levelname == "WARNING" and "XX" in record.message
        for record in caplog.records
    )


async def test_renamed_holiday_falls_back_to_contains_lookup(
    hass: HomeAssistant, create_service_entry
) -> None:
    """A stored name the library has since renamed still resolves.

    holidays >= 0.93 renamed e.g. "Thanksgiving" to "Thanksgiving Day"; the
    exact-match lookup finds nothing, so resolution must fall back to a
    contains-style match before giving up.
    """
    schedules = {
        "thanksgiving": {
            "name": "Thanksgiving",
            "schedule_type": "holiday",
            "country_code": "US",
            "category": "public",
            "holiday_name": "Thanksgiving",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
            "uid": "thanksgiving",
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")
    start = datetime(2026, 11, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2026, 11, 30, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Thanksgiving"
    # Thanksgiving Day 2026 is November 26
    assert events[0].start == date(2026, 11, 26)


def test_no_unintended_base_class_overrides() -> None:
    """Members defined on SchedulerCalendar must not shadow CalendarEntity.

    HA 2026.6 added CalendarEntity._async_update_listener, which the calendar
    dashboard's event subscription invokes. Our options-update listener used
    to share that name with an incompatible signature, so every dashboard
    subscription raised TypeError and the dashboard showed no events. Guard
    against any future accidental shadowing of base-class members.
    """
    from homeassistant.components.calendar import CalendarEntity

    from custom_components.ha_scheduler.calendar import SchedulerCalendar

    intentional_overrides = {
        "_attr_has_entity_name",
        "async_added_to_hass",
        "async_will_remove_from_hass",
        "extra_state_attributes",
        "event",
        "async_get_events",
    }

    shadowed = {
        name
        for name in SchedulerCalendar.__dict__
        if not name.startswith("__")
        and not name.startswith("_abc_")
        and not re.match(r"_[A-Z]", name)  # name-mangled (_ClassName__attr)
        and hasattr(CalendarEntity, name)
        and name not in intentional_overrides
    }

    assert not shadowed, (
        f"SchedulerCalendar unintentionally overrides CalendarEntity members: "
        f"{sorted(shadowed)}"
    )


async def test_legacy_options_layout_still_lists_events(
    hass: HomeAssistant,
) -> None:
    """An entry with the pre-services options layout still serves its events.

    The setup path builds a default service for legacy options, but event
    listing reads live options — it must fall back to the legacy keys instead
    of returning an empty calendar.
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.ha_scheduler.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={"scheduler_name": "Test Scheduler"},
        options={
            "schedules": {
                "date-schedule": {
                    "name": "Summer Schedule",
                    "schedule_type": "date",
                    "start_month": 6,
                    "start_day": 1,
                    "end_month": 8,
                    "end_day": 31,
                    "uid": "date-schedule",
                }
            },
            "configuration": {},
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calendar = hass.data["calendar"].get_entity("calendar.test_scheduler")
    start = datetime(2024, 5, 1, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    end = datetime(2024, 9, 30, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    events = await calendar.async_get_events(hass, start, end)

    assert len(events) == 1
    assert events[0].summary == "Summer Schedule"


async def test_unresolvable_holiday_logs_warning(
    hass: HomeAssistant,
    create_service_entry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A holiday name that resolves to zero dates is reported at warning level."""
    schedules = {
        "ghost-holiday": {
            "name": "Ghost Holiday",
            "schedule_type": "holiday",
            "country_code": "US",
            "category": "public",
            "holiday_name": "Definitely Not A Real Holiday",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
            "uid": "ghost-holiday",
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert any(
        record.levelname == "WARNING"
        and "Definitely Not A Real Holiday" in record.message
        for record in caplog.records
    )
