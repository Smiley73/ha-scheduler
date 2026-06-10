"""End-to-end integration tests for HA Scheduler.

These tests validate complete integration scenarios including migration,
diagnostics, and multi-component interactions.
"""

from datetime import date

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    async def test_v1_to_v2_migration_preserves_functionality(
        self, hass: HomeAssistant
    ):
        """Test V1 data migrates correctly and calendar continues working."""
        # Create V1 config entry with old structure
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Legacy Scheduler",
            data={},
            options={
                "schedules": {
                    "old_schedule": {
                        "name": "Old Schedule",
                        "schedule_type": "date",
                        "start_month": 6,
                        "start_day": 1,
                        "end_month": 8,
                        "end_day": 31,
                    }
                },
                "configuration": {"brightness": 50},
            },
            version=1,  # Old version
        )
        entry.add_to_hass(hass)

        # Setup integration - should trigger migration
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify migration occurred
        updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
        assert updated_entry.version == 2

        # Verify data was migrated correctly
        assert "services" in updated_entry.options
        assert "default" in updated_entry.options["services"]
        default_service = updated_entry.options["services"]["default"]

        # Verify schedule preserved
        assert "schedules" in default_service
        assert len(default_service["schedules"]) == 1
        migrated_schedule = next(iter(default_service["schedules"].values()))
        assert migrated_schedule["name"] == "Old Schedule"
        assert migrated_schedule["start_month"] == 6

        # Verify configuration preserved
        assert "configuration" in default_service
        assert default_service["configuration"]["brightness"] == 50

        # Verify calendar entity still works with same entity_id
        calendar_entity_id = "calendar.legacy_scheduler"
        state = hass.states.get(calendar_entity_id)
        assert state is not None

        # Verify calendar can still generate events with migrated data
        from custom_components.ha_scheduler.schedule_generator import (
            generate_schedule_dates,
        )

        dates = generate_schedule_dates(migrated_schedule, 2024)
        assert len(dates) > 0
        assert dates[0][0] == date(2024, 6, 1)
        assert dates[0][1] == date(2024, 8, 31)

    async def test_diagnostics_integration(self, hass: HomeAssistant):
        """Test diagnostics work with complete integration setup."""
        # Setup integration with schedules
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Scheduler",
            data={"scheduler_name": "Test Scheduler"},
            options={
                "services": {
                    "default": {
                        "name": "Test Scheduler",
                        "schedules": {
                            "schedule1": {
                                "name": "Summer",
                                "schedule_type": "date",
                                "start_month": 6,
                                "start_day": 1,
                                "end_month": 8,
                                "end_day": 31,
                                "uid": "schedule1",
                                "configuration": {"brightness": 75},
                            },
                            "schedule2": {
                                "name": "Winter",
                                "schedule_type": "date",
                                "start_month": 12,
                                "start_day": 1,
                                "end_month": 2,
                                "end_day": 28,
                                "uid": "schedule2",
                            },
                        },
                        "configuration": {"default_brightness": 50},
                    }
                }
            },
            version=2,
            minor_version=1,
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get diagnostics
        from custom_components.ha_scheduler.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

        # Verify diagnostics structure
        assert "entry" in diagnostics
        assert "services" in diagnostics
        assert "summary" in diagnostics

        # Verify service data
        assert "default" in diagnostics["services"]
        default_service = diagnostics["services"]["default"]
        assert default_service["schedules"]["count"] == 2

        # Verify future dates calculated
        schedule_items = default_service["schedules"]["items"]
        assert len(schedule_items) == 2

        for item in schedule_items:
            assert "future_dates" in item
            assert "years" in item["future_dates"]
            # Should have calculated dates for next 3 years
            assert len(item["future_dates"]["years"]) >= 1

        # Verify overlap detection worked
        for item in schedule_items:
            years = item["future_dates"]["years"]
            for year_data in years.values():
                if "overlaps" in year_data:
                    assert "status" in year_data["overlaps"]
                    assert year_data["overlaps"]["status"] in [
                        "no_conflicts",
                        "conflicts_found",
                        "no_dates",
                    ]
