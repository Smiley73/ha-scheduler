"""Shared fixtures and helpers for ha-scheduler tests.

New tests should use the fixtures defined here instead of defining their own
local helpers. Existing tests retain local helpers for backwards compatibility.
"""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN


@pytest.fixture(autouse=True)
async def unload_entries_after_test(hass):
    """Unload all scheduler config entries after each test.

    Home Assistant's calendar component schedules state-transition alarms via
    async_track_point_in_time; they are only cancelled when the entities are
    removed. Without an explicit unload these timers linger past the test and
    trip the strict cleanup verification in pytest-homeassistant-custom-component.
    """
    yield
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def create_service_entry():
    """Factory fixture for creating a service-based MockConfigEntry.

    Usage::

        async def test_something(hass, create_service_entry):
            entry = create_service_entry(schedules={"uid-1": {...}})
            entry.add_to_hass(hass)
    """

    def _factory(
        title: str = "Test Scheduler",
        schedules: dict | None = None,
        configuration: dict | None = None,
    ) -> MockConfigEntry:
        return MockConfigEntry(
            domain=DOMAIN,
            title=title,
            data={"scheduler_name": title},
            options={
                "services": {
                    "default": {
                        "name": title,
                        "schedules": schedules or {},
                        "configuration": configuration or {},
                    }
                }
            },
            version=2,
            minor_version=1,
        )

    return _factory


def get_schedules_from_entry(entry: MockConfigEntry) -> dict:
    """Return the schedules dict from a service-based config entry."""
    return entry.options.get("services", {}).get("default", {}).get("schedules", {})


def get_configuration_from_entry(entry: MockConfigEntry) -> dict:
    """Return the configuration dict from a service-based config entry."""
    return entry.options.get("services", {}).get("default", {}).get("configuration", {})
