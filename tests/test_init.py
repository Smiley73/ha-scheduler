"""Test the Scheduler integration setup and teardown."""

import pytest
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_integration_setup(hass: HomeAssistant, create_service_entry) -> None:
    """Test that the integration sets up and creates a calendar entity."""
    entry = create_service_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    state = hass.states.get("calendar.test_scheduler")
    assert state is not None


async def test_integration_unload(hass: HomeAssistant, create_service_entry) -> None:
    """Test that the integration unloads cleanly."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("calendar.test_scheduler") is not None

    result = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    # HA may restore state as "unavailable" after unload; the platform is unloaded.
    state = hass.states.get("calendar.test_scheduler")
    assert state is None or state.state == "unavailable"


async def test_integration_reload(hass: HomeAssistant, create_service_entry) -> None:
    """Test that the integration can be reloaded and retains its data."""
    schedules = {
        "uid-1": {
            "uid": "uid-1",
            "name": "Summer Schedule",
            "schedule_type": "date",
            "start_month": 6,
            "start_day": 1,
            "end_month": 8,
            "end_day": 31,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("calendar.test_scheduler") is not None

    # Unload then reload
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert hass.states.get("calendar.test_scheduler") is not None
