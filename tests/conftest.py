"""Fixtures for Scheduler integration tests."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.scheduler.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


@pytest.fixture
def hub_entry():
    """Create a mock hub config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={
            "schedules": {
                "test_schedule_1": {
                    "name": "Test Schedule",
                    "start_month": 1,
                    "end_month": 12,
                    "schedule_type": "date",
                    "start_day": 1,
                    "end_day": 15,
                },
            },
        },
        entry_id="test_hub_entry_id",
    )


@pytest.fixture
def empty_hub_entry():
    """Create a mock hub config entry with no schedules."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Scheduler",
        data={"schedules": {}},
        entry_id="test_empty_hub_id",
    )
