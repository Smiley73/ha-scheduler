"""Test calendar description formatting functionality."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.calendar import SchedulerCalendar
from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def test_format_config_description_empty():
    """Test formatting empty configuration."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test", data={}, options={})
    calendar = SchedulerCalendar(entry)

    result = calendar._format_config_description({})
    assert result == ""

    result = calendar._format_config_description(None)
    assert result == ""


def test_format_config_description_simple():
    """Test formatting simple key-value pairs."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test", data={}, options={})
    calendar = SchedulerCalendar(entry)

    config = {"mode": "vacation", "temperature": 72, "enabled": True}

    result = calendar._format_config_description(config)
    lines = result.split("\n")

    assert "mode: vacation" in lines
    assert "temperature: 72" in lines
    assert "enabled: True" in lines


def test_format_config_description_nested_dict():
    """Test formatting nested dictionaries."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test", data={}, options={})
    calendar = SchedulerCalendar(entry)

    config = {"settings": {"temperature": 72, "mode": "auto"}, "name": "Test Schedule"}

    result = calendar._format_config_description(config)

    assert "name: Test Schedule" in result
    assert "settings:" in result
    assert '"temperature": 72' in result
    assert '"mode": "auto"' in result


def test_format_config_description_list():
    """Test formatting lists."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test", data={}, options={})
    calendar = SchedulerCalendar(entry)

    config = {"days": ["monday", "tuesday", "friday"], "temperatures": [68, 72, 70]}

    result = calendar._format_config_description(config)

    assert "days: monday, tuesday, friday" in result
    assert "temperatures: 68, 72, 70" in result


def test_format_config_description_mixed():
    """Test formatting mixed data types."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test", data={}, options={})
    calendar = SchedulerCalendar(entry)

    config = {
        "name": "Complex Schedule",
        "settings": {"temp": 72, "mode": "heat"},
        "days": ["mon", "wed", "fri"],
        "enabled": True,
        "priority": 1,
    }

    result = calendar._format_config_description(config)
    lines = result.split("\n")

    # Check that all types are handled
    assert any("name: Complex Schedule" in line for line in lines)
    assert any("settings:" in line for line in lines)
    assert any("days: mon, wed, fri" in line for line in lines)
    assert any("enabled: True" in line for line in lines)
    assert any("priority: 1" in line for line in lines)
