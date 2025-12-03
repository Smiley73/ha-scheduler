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
def config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Schedule",
        data={
            "name": "Test Schedule",
            "start_month": "january",
            "end_month": "december",
        },
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
