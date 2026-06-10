"""Comprehensive tests for holiday import functionality."""

from datetime import date
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN
from custom_components.ha_scheduler.holiday_importer import (
    _analyze_week_pattern,
    analyze_holiday_pattern,
    calculate_occurrence,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={"scheduler_name": "Test Scheduler"},
        options={
            "services": {
                "default": {
                    "name": "Test Scheduler",
                    "schedules": {},
                }
            }
        },
        version=2,
        minor_version=1,
    )


@pytest.fixture
def mock_existing_schedules_config_entry():
    """Return a mock config entry with existing schedules."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={"scheduler_name": "Test Scheduler"},
        options={
            "services": {
                "default": {
                    "name": "Test Scheduler",
                    "schedules": {
                        "existing_schedule": {
                            "name": "Existing Schedule",
                            "schedule_type": "date",
                            "start_month": 1,
                            "start_day": 1,
                            "end_month": 1,
                            "end_day": 1,
                        },
                        "independence_day": {
                            "name": "Independence Day",
                            "schedule_type": "date",
                            "start_month": 7,
                            "start_day": 4,
                            "end_month": 7,
                            "end_day": 4,
                        },
                    },
                }
            }
        },
        version=2,
        minor_version=1,
    )


class TestHolidayImportDefaults:
    """Test holiday import default behavior."""

    async def test_holiday_import_all_holidays_default(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test that holiday import defaults to selecting all holidays."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        mock_holidays = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 7,
                    "start_day": 4,
                    "end_month": 7,
                    "end_day": 4,
                    "description": "Fixed date: July 4",
                },
            },
            "Labor Day": {
                "name": "Labor Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "nth-day",
                    "month": 9,
                    "occurrence": 0,
                    "day_of_week": 0,
                    "start_offset": 0,
                    "end_offset": 0,
                    "description": "First Monday of September",
                },
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            # Start options flow and navigate to holiday selection
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )

            # Import without specifying holidays (should default to all)
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY

            # Check that both schedules were created
            updated_entry = hass.config_entries.async_get_entry(
                mock_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]

            assert len(schedules) == 2
            schedule_names = [schedule["name"] for schedule in schedules.values()]
            assert "Independence Day" in schedule_names
            assert "Labor Day" in schedule_names
            assert all(
                schedule["schedule_type"] == "holiday"
                for schedule in schedules.values()
            )

    async def test_holiday_import_no_country_name_default(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test that holiday import defaults to not including country names."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        mock_holidays = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 7,
                    "start_day": 4,
                    "end_month": 7,
                    "end_day": 4,
                    "description": "Fixed date: July 4",
                },
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            # Start options flow and navigate to holiday selection
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )

            # Import with explicit include_country_name=False
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Independence Day"],
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY

            # Check that schedule was created without country name
            updated_entry = hass.config_entries.async_get_entry(
                mock_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]

            assert len(schedules) == 1
            schedule = next(iter(schedules.values()))
            assert schedule["name"] == "Independence Day"  # No "(US)" suffix
            assert schedule["schedule_type"] == "holiday"
            assert schedule["country_code"] == "US"
            assert schedule["category"] == "public"
            assert schedule["holiday_name"] == "Independence Day"

    async def test_holiday_import_variable_holiday_creates_holiday_schedule(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test movable holidays import as holiday-backed schedules."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        mock_holidays = {
            "Good Friday": {
                "name": "Good Friday",
                "category": "public",
                "dates": [date(2026, 4, 3)],
                "pattern": {
                    "schedule_type": "holiday",
                    "country_code": "DE",
                    "category": "public",
                    "holiday_name": "Good Friday",
                    "name_lookup": "iexact",
                    "start_offset": 0,
                    "end_offset": 0,
                    "description": "Holiday-backed (resolved each year)",
                },
            }
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"DE": "Germany"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "DE"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Good Friday"],
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                },
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY

        updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
        schedules = updated_entry.options["services"]["default"]["schedules"]

        assert len(schedules) == 1
        schedule = next(iter(schedules.values()))
        assert schedule["name"] == "Good Friday"
        assert schedule["schedule_type"] == "holiday"
        assert schedule["country_code"] == "DE"
        assert schedule["category"] == "public"
        assert schedule["holiday_name"] == "Good Friday"

    async def test_holiday_import_use_holiday_type_for_fixed_date(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test fixed-date holidays can be imported as holiday-backed schedules."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        mock_holidays = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [date(2026, 7, 4)],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 7,
                    "start_day": 4,
                    "end_month": 7,
                    "end_day": 4,
                    "description": "Fixed date: July 4",
                },
            }
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Independence Day"],
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                    "use_holiday_type": True,
                },
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY

        updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
        schedules = updated_entry.options["services"]["default"]["schedules"]

        assert len(schedules) == 1
        schedule = next(iter(schedules.values()))
        assert schedule["name"] == "Independence Day"
        assert schedule["schedule_type"] == "holiday"
        assert schedule["country_code"] == "US"
        assert schedule["category"] == "public"
        assert schedule["holiday_name"] == "Independence Day"
        assert schedule["name_lookup"] == "iexact"


class TestHolidayImportOptions:
    """Test various holiday import options."""

    async def test_holiday_import_with_country_name(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test holiday import with country name included."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        mock_holidays = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 7,
                    "start_day": 4,
                    "end_month": 7,
                    "end_day": 4,
                    "description": "Fixed date: July 4",
                },
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )

            # Import with country name included
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Independence Day"],
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": True,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY

            updated_entry = hass.config_entries.async_get_entry(
                mock_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]

            assert len(schedules) == 1
            schedule = next(iter(schedules.values()))
            assert schedule["name"] == "Independence Day (US)"

    async def test_holiday_import_overwrite_existing(
        self, hass: HomeAssistant, mock_existing_schedules_config_entry
    ):
        """Test holiday import with overwrite existing option."""
        mock_existing_schedules_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(
            mock_existing_schedules_config_entry.entry_id
        )

        mock_holidays = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 7,
                    "start_day": 5,  # Different day to test overwrite
                    "end_month": 7,
                    "end_day": 5,
                    "description": "Fixed date: July 05",
                },
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_existing_schedules_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )

            # Import with overwrite enabled
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Independence Day"],
                    "overwrite_existing": True,
                    "skip_on_overlap": False,
                    "include_country_name": False,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY

            updated_entry = hass.config_entries.async_get_entry(
                mock_existing_schedules_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]

            # Should still have 2 schedules (existing + overwritten)
            assert len(schedules) == 2

            # Find the Independence Day schedule and verify it was overwritten
            independence_schedule = None
            for schedule in schedules.values():
                if schedule["name"] == "Independence Day":
                    independence_schedule = schedule
                    break

            assert independence_schedule is not None
            assert independence_schedule["schedule_type"] == "holiday"
            assert independence_schedule["country_code"] == "US"
            assert independence_schedule["category"] == "public"
            assert independence_schedule["holiday_name"] == "Independence Day"

    async def test_holiday_import_overwrite_existing_with_legacy_schedule_uid_fallback(
        self, hass: HomeAssistant, mock_existing_schedules_config_entry
    ):
        """Test overwrite works for legacy schedules without embedded uid fields."""
        mock_existing_schedules_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(
            mock_existing_schedules_config_entry.entry_id
        )

        mock_holidays = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 7,
                    "start_day": 5,
                    "end_month": 7,
                    "end_day": 5,
                    "description": "Fixed date: July 05",
                },
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_existing_schedules_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Independence Day"],
                    "overwrite_existing": True,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                    "use_holiday_type": False,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY

            updated_entry = hass.config_entries.async_get_entry(
                mock_existing_schedules_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]

            independence_schedule = schedules["independence_day"]
            assert independence_schedule["start_day"] == 5
            assert independence_schedule["uid"] == "independence_day"

    async def test_holiday_import_skip_existing_name(
        self, hass: HomeAssistant, mock_existing_schedules_config_entry
    ):
        """Test holiday import when schedule name already exists and overwrite is disabled."""
        mock_existing_schedules_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(
            mock_existing_schedules_config_entry.entry_id
        )

        mock_holidays = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 7,
                    "start_day": 5,  # Different day
                    "end_month": 7,
                    "end_day": 5,
                    "description": "Fixed date: July 05",
                },
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_existing_schedules_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )

            # Import with overwrite disabled - should show form with error since name exists
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Independence Day"],
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                },
            )

            # Should return to form with error since nothing was imported (name conflict)
            assert result["type"] == FlowResultType.FORM
            assert "errors" in result
            assert "base" in result["errors"]
            assert result["errors"]["base"] == "no_holidays_imported"

            # Original schedules should remain unchanged
            updated_entry = hass.config_entries.async_get_entry(
                mock_existing_schedules_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]

            # Should still have 2 schedules (nothing imported)
            assert len(schedules) == 2

            # Find the Independence Day schedule and verify it was NOT changed
            independence_schedule = None
            for schedule in schedules.values():
                if schedule["name"] == "Independence Day":
                    independence_schedule = schedule
                    break

            assert independence_schedule is not None
            assert independence_schedule["start_day"] == 4  # Should remain original

    async def test_holiday_import_new_holiday_no_overlap(
        self, hass: HomeAssistant, mock_existing_schedules_config_entry
    ):
        """Test holiday import with a new holiday that doesn't overlap."""
        mock_existing_schedules_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(
            mock_existing_schedules_config_entry.entry_id
        )

        mock_holidays = {
            "Labor Day": {
                "name": "Labor Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "nth-day",
                    "month": 9,
                    "occurrence": 0,
                    "day_of_week": 0,
                    "start_offset": 0,
                    "end_offset": 0,
                    "description": "First Monday of September",
                },
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_existing_schedules_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )

            # Import new holiday that doesn't conflict
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Labor Day"],
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                    "use_holiday_type": False,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY

            updated_entry = hass.config_entries.async_get_entry(
                mock_existing_schedules_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]

            # Should now have 3 schedules (2 existing + 1 new)
            assert len(schedules) == 3

            # Check that Labor Day was added
            schedule_names = [schedule["name"] for schedule in schedules.values()]
            assert "Labor Day" in schedule_names
            assert "Independence Day" in schedule_names
            assert "Existing Schedule" in schedule_names

    async def test_holiday_import_multiple_categories(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test holiday import with multiple categories."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        mock_holidays = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 7,
                    "start_day": 4,
                    "end_month": 7,
                    "end_day": 4,
                    "description": "Fixed date: July 4",
                },
            },
            "Bank Holiday": {
                "name": "Bank Holiday",
                "category": "bank",
                "dates": [],
                "pattern": {
                    "schedule_type": "date",
                    "start_month": 5,
                    "start_day": 1,
                    "end_month": 5,
                    "end_day": 1,
                    "description": "Fixed date: May 01",
                },
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays", "bank": "Bank Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public", "bank"]}
            )

            # Import all holidays from both categories
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                    "use_holiday_type": False,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY

            updated_entry = hass.config_entries.async_get_entry(
                mock_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]

            assert len(schedules) == 2
            schedule_names = [schedule["name"] for schedule in schedules.values()]
            assert "Independence Day" in schedule_names
            assert "Bank Holiday" in schedule_names


class TestHolidayPatternAnalysis:
    """Test holiday pattern analysis functionality."""

    def test_analyze_fixed_date_pattern(self):
        """Test analyzing fixed date holidays (e.g., Christmas, Independence Day)."""
        # Independence Day: July 4th
        dates = [
            date(2023, 7, 4),
            date(2024, 7, 4),
            date(2025, 7, 4),
        ]

        pattern = analyze_holiday_pattern(dates)

        assert pattern is not None
        assert pattern["schedule_type"] == "date"
        assert pattern["start_month"] == 7
        assert pattern["start_day"] == 4
        assert pattern["end_month"] == 7
        assert pattern["end_day"] == 4
        assert "Fixed date: July 4" in pattern["description"]

    def test_analyze_nth_day_pattern(self):
        """Test analyzing nth-day holidays (e.g., Memorial Day, Labor Day)."""
        # Memorial Day: Last Monday of May
        dates = [
            date(2023, 5, 29),  # Last Monday of May 2023
            date(2024, 5, 27),  # Last Monday of May 2024
            date(2025, 5, 26),  # Last Monday of May 2025
        ]

        pattern = analyze_holiday_pattern(dates)

        assert pattern is not None
        assert pattern["schedule_type"] == "nth-day"
        assert pattern["month"] == 5
        assert pattern["occurrence"] == 4  # Last (4)
        assert pattern["day_of_week"] == 0  # Monday
        assert "Last Monday of May" in pattern["description"]

    def test_analyze_week_pattern_single_week(self):
        """Test analyzing a pattern that spans multiple days in the same week."""
        # Spring break: Monday to Friday of the first week of March
        dates = [
            date(2023, 3, 6),  # Monday, first occurrence
            date(2023, 3, 7),  # Tuesday
            date(2023, 3, 8),  # Wednesday
            date(2023, 3, 9),  # Thursday
            date(2023, 3, 10),  # Friday, second occurrence
            date(2024, 3, 4),  # Monday, first occurrence
            date(2024, 3, 5),  # Tuesday
            date(2024, 3, 6),  # Wednesday
            date(2024, 3, 7),  # Thursday
            date(2024, 3, 8),  # Friday, second occurrence
        ]

        pattern = _analyze_week_pattern(dates)

        assert pattern is not None
        assert pattern["schedule_type"] == "week"
        assert pattern["start_month"] == 3
        assert pattern["start_week"] == 0  # First occurrence of Monday
        assert pattern["start_week_type"] == "partial"
        assert pattern["start_day_of_week"] == 0  # Monday
        assert pattern["end_month"] == 3
        assert pattern["end_week"] == 1  # Second occurrence of Friday
        assert pattern["end_day_of_week"] == 4  # Friday

    def test_analyze_week_pattern_cross_weeks(self):
        """Test analyzing a pattern that spans across different weeks."""
        # First Friday to First Monday (same occurrence numbers)
        dates = [
            date(2023, 3, 3),  # Friday, first occurrence
            date(2023, 3, 4),  # Saturday
            date(2023, 3, 5),  # Sunday
            date(2023, 3, 6),  # Monday, first occurrence
            date(2024, 3, 1),  # Friday, first occurrence
            date(2024, 3, 2),  # Saturday
            date(2024, 3, 3),  # Sunday
            date(2024, 3, 4),  # Monday, first occurrence
        ]

        pattern = _analyze_week_pattern(dates)

        assert pattern is not None
        assert pattern["schedule_type"] == "week"
        assert pattern["start_month"] == 3
        assert pattern["start_week"] == 0  # First occurrence
        assert pattern["start_week_type"] == "partial"
        assert pattern["start_day_of_week"] == 4  # Friday
        assert pattern["end_month"] == 3
        assert pattern["end_week"] == 0  # First occurrence
        assert pattern["end_week_type"] == "partial"
        assert pattern["end_day_of_week"] == 0  # Monday

    def test_analyze_week_pattern_inconsistent(self):
        """Test that inconsistent patterns return None."""
        # Dates that don't follow a consistent week pattern
        dates = [
            date(2023, 3, 6),  # Monday, first week of March 2023
            date(2023, 3, 7),  # Tuesday
            date(2024, 3, 15),  # Different week in 2024
            date(2024, 3, 16),  # Different week in 2024
        ]

        pattern = _analyze_week_pattern(dates)
        assert pattern is None

    def test_analyze_week_pattern_insufficient_data(self):
        """Test that insufficient data returns None."""
        # Only one date
        dates = [date(2023, 3, 6)]
        pattern = _analyze_week_pattern(dates)
        assert pattern is None

        # Only one year
        dates = [date(2023, 3, 6), date(2023, 3, 7)]
        pattern = _analyze_week_pattern(dates)
        assert pattern is None

    def test_analyze_holiday_pattern_prefers_week_over_nth_day(self):
        """Test that analyze_holiday_pattern can detect week patterns."""
        # Spring break: Monday to Friday spanning first and second week occurrences
        dates = [
            date(2023, 3, 6),  # Monday, first occurrence
            date(2023, 3, 7),  # Tuesday
            date(2023, 3, 8),  # Wednesday
            date(2023, 3, 9),  # Thursday
            date(2023, 3, 10),  # Friday, second occurrence
            date(2024, 3, 4),  # Monday, first occurrence
            date(2024, 3, 5),  # Tuesday
            date(2024, 3, 6),  # Wednesday
            date(2024, 3, 7),  # Thursday
            date(2024, 3, 8),  # Friday, second occurrence
        ]

        pattern = analyze_holiday_pattern(dates)

        # Should detect as week pattern since it spans multiple consecutive days
        assert pattern is not None
        assert pattern["schedule_type"] == "week"
        assert "March" in pattern["description"]

    def test_analyze_holiday_pattern_single_day_remains_nth_day(self):
        """Test that single-day holidays still use nth-day pattern."""
        # Memorial Day: Last Monday of May
        dates = [
            date(2023, 5, 29),  # Last Monday of May 2023
            date(2024, 5, 27),  # Last Monday of May 2024
            date(2025, 5, 26),  # Last Monday of May 2025
        ]

        pattern = analyze_holiday_pattern(dates)

        # Should remain as nth-day pattern for single-day holidays
        assert pattern is not None
        assert pattern["schedule_type"] == "nth-day"
        assert pattern["occurrence"] == 4  # Last
        assert pattern["day_of_week"] == 0  # Monday

    def test_analyze_single_date_pattern(self):
        """Test analyzing a pattern with only one date."""
        dates = [date(2023, 12, 25)]

        pattern = analyze_holiday_pattern(dates)

        assert pattern is not None
        assert pattern["schedule_type"] == "date"
        assert pattern["start_month"] == 12
        assert pattern["start_day"] == 25
        assert "Fixed date: December 25" in pattern["description"]

    def test_analyze_variable_date_fallback(self):
        """Test fallback for dates that don't match any pattern."""
        # Random dates that don't follow a pattern
        dates = [
            date(2023, 3, 15),  # Random date
            date(2024, 5, 22),  # Different month/day
            date(2025, 8, 10),  # Another different date
        ]

        pattern = analyze_holiday_pattern(dates)

        assert pattern is not None
        assert pattern["schedule_type"] == "date"
        assert pattern["start_month"] == 3  # Uses first date
        assert pattern["start_day"] == 15
        assert "Variable date" in pattern["description"]


class TestCalculateOccurrence:
    """Test occurrence calculation functionality."""

    def test_calculate_first_occurrence(self):
        """Test calculating first occurrence of weekday in month."""
        # First Monday of March 2023 (March 6)
        result = calculate_occurrence(date(2023, 3, 6))
        assert result == 0

    def test_calculate_second_occurrence(self):
        """Test calculating second occurrence of weekday in month."""
        # Second Monday of March 2023 (March 13)
        result = calculate_occurrence(date(2023, 3, 13))
        assert result == 1

    def test_calculate_last_occurrence(self):
        """Test calculating last occurrence of weekday in month."""
        # Last Monday of May 2023 (May 29)
        result = calculate_occurrence(date(2023, 5, 29))
        assert result == 4  # Last occurrence is represented as 4

    def test_calculate_occurrence_edge_cases(self):
        """Test occurrence calculation edge cases."""
        # Test various edge cases

        # First day of month that's also first occurrence
        result = calculate_occurrence(date(2023, 4, 3))  # First Monday of April 2023
        assert result == 0

        # Last day of month that's also last occurrence
        result = calculate_occurrence(date(2023, 4, 30))  # Last Sunday of April 2023
        assert result == 4


class TestHolidayImportErrorHandling:
    """Test error handling in holiday import."""

    async def test_holiday_import_no_holidays_library(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test holiday import when holidays library is not available."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE",
                False,
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={},
            ),
        ):
            # Should handle gracefully when holidays library is not available
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )

            # Should show error or empty country list
            assert result["type"] in [FlowResultType.FORM, FlowResultType.ABORT]

    async def test_holiday_import_empty_holidays(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test holiday import when no holidays are available."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value={},  # No holidays available
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )

            # When no holidays are available, submitting empty list should show error
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": [],  # Empty list when no holidays available
                },
            )

            # Should return to form with error since nothing was imported
            assert result["type"] == FlowResultType.FORM
            assert "errors" in result
            assert "holidays" in result["errors"]
            assert result["errors"]["holidays"] == "no_holidays_selected"

            # Original schedules should remain unchanged
            updated_entry = hass.config_entries.async_get_entry(
                mock_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]
            assert len(schedules) == 0

    async def test_holiday_import_invalid_pattern(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test holiday import fails without a usable pattern when disabled."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        mock_holidays = {
            "Invalid Holiday": {
                "name": "Invalid Holiday",
                "category": "public",
                "dates": [],  # No dates - should cause pattern analysis to fail
                "pattern": None,
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )

            # Should handle invalid patterns gracefully - returns to form with error
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": [
                        "Invalid Holiday"
                    ],  # Select the holiday with invalid pattern
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                    "use_holiday_type": False,
                },
            )

            # Should return to form with error since pattern is invalid
            assert result["type"] == FlowResultType.FORM
            assert "errors" in result
            assert "base" in result["errors"]
            assert result["errors"]["base"] == "no_holidays_imported"

            # Should not add schedules with invalid patterns
            updated_entry = hass.config_entries.async_get_entry(
                mock_config_entry.entry_id
            )
            schedules = updated_entry.options["services"]["default"]["schedules"]
            assert len(schedules) == 0

    async def test_holiday_import_invalid_pattern_with_holiday_type(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test the holiday import toggle bypasses missing pattern analysis."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        mock_holidays = {
            "Invalid Holiday": {
                "name": "Invalid Holiday",
                "category": "public",
                "dates": [],
                "pattern": None,
            },
        }

        with (
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
                return_value={"US": "United States"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_available_categories",
                return_value={"public": "Public Holidays"},
            ),
            patch(
                "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
                return_value=mock_holidays,
            ),
        ):
            result = await hass.config_entries.options.async_init(
                mock_config_entry.entry_id
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "import_holidays"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"country": "US"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"categories": ["public"]}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "holidays": ["Invalid Holiday"],
                    "overwrite_existing": False,
                    "skip_on_overlap": True,
                    "include_country_name": False,
                    "use_holiday_type": True,
                },
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY

        updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
        schedules = updated_entry.options["services"]["default"]["schedules"]
        assert len(schedules) == 1

        schedule = next(iter(schedules.values()))
        assert schedule["name"] == "Invalid Holiday"
        assert schedule["schedule_type"] == "holiday"
        assert schedule["country_code"] == "US"
        assert schedule["category"] == "public"
        assert schedule["holiday_name"] == "Invalid Holiday"
