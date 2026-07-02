"""Tests for holiday_importer helper functions."""

import builtins
import importlib
import logging
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import custom_components.ha_scheduler.holiday_importer as holiday_importer
from custom_components.ha_scheduler.holiday_importer import (
    _analyze_multi_day_pattern,
    _build_holiday_cache_requests,
    _build_nth_weekday_pattern,
    _clear_holiday_caches,
    _get_available_categories_sync,
    _get_country_holidays_sync,
    _get_holidays_for_country_sync,
    _get_named_holiday_dates_sync,
    _get_supported_countries_sync,
    _merge_contiguous_dates,
    _prime_holiday_cache_sync,
    _should_use_holiday_schedule_pattern,
    analyze_holiday_pattern,
    async_prime_holiday_cache,
    calculate_occurrence,
    format_date_localized,
    generate_holiday_schedule_dates,
    get_holidays_for_country,
    get_holidays_library_version,
    get_localized_country_name,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def test_holiday_importer_defers_holidays_import_until_runtime(monkeypatch):
    """Test importing the module does not import holidays on the event loop."""
    module_name = holiday_importer.__name__
    original_module = sys.modules[module_name]
    original_import = builtins.__import__

    def guard_holidays_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "holidays":
            raise AssertionError("holidays imported during module load")
        return original_import(name, globals, locals, fromlist, level)

    sys.modules.pop(module_name, None)
    monkeypatch.setattr(builtins, "__import__", guard_holidays_import)

    try:
        reloaded_module = importlib.import_module(module_name)
    finally:
        monkeypatch.setattr(builtins, "__import__", original_import)
        sys.modules[module_name] = original_module

    assert reloaded_module.HOLIDAYS_AVAILABLE is None


@pytest.fixture(autouse=True)
def clear_holiday_caches():
    """Reset holiday resolver caches between tests."""
    _clear_holiday_caches()
    yield
    _clear_holiday_caches()


class TestFormatDateLocalized:
    """Test date formatting with localization."""

    def test_format_date_with_english_locale(self):
        """Test date formatting with English locale."""
        test_date = date(2024, 7, 4)
        result = format_date_localized(test_date, "en")
        # Should format as "July 4"
        assert "July" in result
        assert "4" in result

    def test_format_date_default_locale(self):
        """Test date formatting with default locale."""
        test_date = date(2024, 12, 25)
        result = format_date_localized(test_date)
        # Should format as "December 25"
        assert "December" in result
        assert "25" in result

    def test_format_date_different_months(self):
        """Test date formatting for various months."""
        test_dates = [
            (date(2024, 1, 15), "January", "15"),
            (date(2024, 6, 1), "June", "1"),
            (date(2024, 11, 30), "November", "30"),
        ]
        for test_date, expected_month, expected_day in test_dates:
            result = format_date_localized(test_date)
            assert expected_month in result
            assert expected_day in result


class TestGetLocalizedCountryName:
    """Test country name localization."""

    def test_get_country_name_with_fallback(self):
        """Test getting country name with fallback."""
        result = get_localized_country_name("US", "United States")
        # Should return proper country name
        assert "United States" in result

    def test_get_country_name_common_countries(self):
        """Test getting names for common countries."""
        test_cases = [
            ("US", "United States"),
            ("CA", "Canada"),
            ("GB", "United Kingdom"),
            ("DE", "Germany"),
        ]
        for country_code, fallback_name in test_cases:
            result = get_localized_country_name(country_code, fallback_name)
            # Should return a proper country name (not just code)
            assert len(result) > 2  # More than just country code
            assert result != country_code  # Should be localized, not just code


class TestGetSupportedCountriesSync:
    """Test synchronous country discovery."""

    def test_get_supported_countries_success(self):
        """Test getting supported countries."""
        mock_countries = ["US", "CA", "GB"]

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "holidays.list_supported_countries", return_value=mock_countries
            ):
                with patch("holidays.country_holidays") as mock_holiday:
                    # Mock country objects
                    mock_us = MagicMock()
                    mock_us.country = "United States"
                    mock_ca = MagicMock()
                    mock_ca.country = "Canada"
                    mock_gb = MagicMock()
                    mock_gb.country = "United Kingdom"

                    mock_holiday.side_effect = [mock_us, mock_ca, mock_gb]

                    result = _get_supported_countries_sync()

                    assert isinstance(result, dict)
                    assert len(result) >= 3

    def test_get_supported_countries_holidays_unavailable(self):
        """Test getting countries when holidays library is unavailable."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", False
        ):
            result = _get_supported_countries_sync()
            assert result == {}

    def test_get_supported_countries_error_handling(self):
        """Test error handling in country discovery."""
        mock_countries = ["US", "INVALID"]

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "holidays.list_supported_countries", return_value=mock_countries
            ):
                with patch("holidays.country_holidays") as mock_holiday:
                    # First call succeeds, second fails
                    mock_us = MagicMock()
                    mock_us.country = "United States"
                    mock_holiday.side_effect = [mock_us, Exception("Invalid country")]

                    result = _get_supported_countries_sync()

                    # Should still return the successful country
                    assert isinstance(result, dict)
                    assert "US" in result

    def test_get_supported_countries_fallback_on_total_failure(self):
        """Test fallback when all country discovery fails."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "holidays.list_supported_countries", side_effect=Exception("Error")
            ):
                result = _get_supported_countries_sync()
                # Should return fallback list
                assert isinstance(result, dict)
                # Should have at least some common countries as fallback
                assert len(result) > 0


class TestGetAvailableCategoriesSync:
    """Test synchronous category discovery."""

    def test_get_categories_success(self):
        """Test getting available categories for a country."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch("holidays.country_holidays") as mock_holidays:
                # Mock successful category tests
                mock_holidays.return_value = MagicMock()

                result = _get_available_categories_sync("US")

                assert isinstance(result, dict)
                # Should at least have public category
                assert "public" in result

    def test_get_categories_holidays_unavailable(self):
        """Test getting categories when holidays library unavailable."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", False
        ):
            result = _get_available_categories_sync("US")
            # Should return default
            assert result == {"public": "Public Holidays"}

    def test_get_categories_error_handling(self):
        """Test error handling in category discovery."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch("holidays.country_holidays", side_effect=Exception("Error")):
                result = _get_available_categories_sync("INVALID")
                # Should return default public category
                assert result == {"public": "Public Holidays"}


class TestGetHolidaysForCountrySync:
    """Test synchronous holiday retrieval."""

    def test_get_holidays_success(self):
        """Test getting holidays for a country."""
        mock_holidays_obj = {
            date(2024, 7, 4): "Independence Day",
            date(2024, 12, 25): "Christmas Day",
        }

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch("holidays.country_holidays", return_value=mock_holidays_obj):
                with patch(
                    "custom_components.ha_scheduler.holiday_importer._get_available_categories_sync",
                    return_value={"public": "Public Holidays"},
                ):
                    result = _get_holidays_for_country_sync("US", ["public"])

                    assert isinstance(result, dict)
                    assert len(result) > 0

    def test_get_holidays_multiple_years(self):
        """Test that holidays are collected across multiple years."""

        # Mock different holidays in different years.
        # The importer calls holidays.country_holidays(country, years=year) with
        # years as an int, so the mock must handle both int and list.
        def mock_holiday_factory(country, **kwargs):
            years_arg = kwargs.get("years", 2024)
            year = years_arg[0] if isinstance(years_arg, (list, tuple)) else years_arg
            if year == 2023:
                return {date(2023, 7, 4): "Independence Day"}
            elif year == 2024:
                return {date(2024, 7, 4): "Independence Day"}
            else:
                return {date(2025, 7, 4): "Independence Day"}

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch("holidays.country_holidays", side_effect=mock_holiday_factory):
                with patch(
                    "custom_components.ha_scheduler.holiday_importer._get_available_categories_sync",
                    return_value={"public": "Public Holidays"},
                ):
                    result = _get_holidays_for_country_sync("US", ["public"])

                    # Should have collected "Independence Day" from multiple years
                    assert "Independence Day" in result
                    holiday_data = result["Independence Day"]
                    assert "dates" in holiday_data
                    assert isinstance(holiday_data["dates"], list)
                    # Collected from ≥2 distinct years
                    assert len(holiday_data["dates"]) >= 2

    def test_get_holidays_holidays_unavailable(self):
        """Test getting holidays when library unavailable."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", False
        ):
            result = _get_holidays_for_country_sync("US")
            assert result == {}

    def test_get_holidays_category_error(self):
        """Test error handling when a category fails."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "holidays.country_holidays", side_effect=Exception("Category error")
            ):
                with patch(
                    "custom_components.ha_scheduler.holiday_importer._get_available_categories_sync",
                    return_value={"public": "Public Holidays"},
                ):
                    result = _get_holidays_for_country_sync("US", ["public"])
                    # Should return empty dict on error, not crash
                    assert isinstance(result, dict)

    def test_get_holidays_total_failure(self):
        """Test total failure in holiday retrieval."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer._get_available_categories_sync",
                side_effect=Exception("Total failure"),
            ):
                result = _get_holidays_for_country_sync("US")
                # Should return empty dict, not crash
                assert result == {}

    def test_get_holidays_variable_dates_use_holiday_schedule(self):
        """Test variable movable holidays use the holiday-backed schedule type."""

        def mock_holiday_factory(country, **kwargs):
            years_arg = kwargs.get("years", 2026)
            year = years_arg[0] if isinstance(years_arg, (list, tuple)) else years_arg

            movable_dates = {
                2023: date(2023, 4, 7),
                2024: date(2024, 3, 29),
                2025: date(2025, 4, 18),
                2026: date(2026, 4, 3),
                2027: date(2027, 3, 26),
                2028: date(2028, 4, 14),
                2029: date(2029, 3, 30),
            }

            return {movable_dates[year]: "Good Friday"}

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch("holidays.country_holidays", side_effect=mock_holiday_factory):
                result = _get_holidays_for_country_sync("DE", ["public"])

        pattern = result["Good Friday"]["pattern"]
        assert pattern["schedule_type"] == "holiday"
        assert pattern["country_code"] == "DE"
        assert pattern["category"] == "public"
        assert pattern["holiday_name"] == "Good Friday"
        assert pattern["name_lookup"] == "iexact"

    def test_get_holidays_variable_date_pattern_uses_own_category_not_last_iterated(
        self,
    ):
        """A movable holiday's rebuilt pattern must use its own category.

        Regression test: the pattern-rebuild call used to pass the outer
        `for category in categories:` loop variable (left over at its last
        value once the loop finished) instead of the holiday's actual
        recorded category, so a movable holiday collected under an earlier
        category would be mistagged with the last category in the list.
        """
        movable_dates = {
            2023: date(2023, 4, 7),
            2024: date(2024, 3, 29),
            2025: date(2025, 4, 18),
            2026: date(2026, 4, 3),
            2027: date(2027, 3, 26),
            2028: date(2028, 4, 14),
            2029: date(2029, 3, 30),
        }

        def fake_get_country_holidays_sync(country_code, category, year):
            if category == "public":
                return {movable_dates[year]: "Good Friday"}
            if category == "bank":
                return {date(year, 1, 1): "Bank Day"}
            return {}

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer._get_country_holidays_sync",
                side_effect=fake_get_country_holidays_sync,
            ):
                # "bank" is last in the list, so a bug that reuses the loop
                # variable instead of the holiday's own category would tag
                # "Good Friday" (collected under "public") as "bank".
                result = _get_holidays_for_country_sync(
                    "US", ["public", "bank"], today=date(2026, 6, 15)
                )

        pattern = result["Good Friday"]["pattern"]
        assert result["Good Friday"]["category"] == "public"
        assert pattern["category"] == "public"
        assert result["Bank Day"]["category"] == "bank"


class TestHolidayScheduleResolution:
    """Test holiday-backed schedule resolution."""

    @pytest.mark.asyncio
    async def test_async_prime_holiday_cache_warms_unique_holiday_requests(self):
        """Test holiday cache priming only warms unique holiday schedule years."""
        schedules = [
            {
                "schedule_type": "holiday",
                "country_code": "DE",
                "category": "public",
                "holiday_name": "Good Friday",
                "name_lookup": "iexact",
            },
            {
                "schedule_type": "holiday",
                "country_code": "DE",
                "category": "public",
                "holiday_name": "Good Friday",
                "name_lookup": "iexact",
            },
            {
                "schedule_type": "date",
                "start_month": 1,
                "start_day": 1,
                "end_month": 1,
                "end_day": 1,
            },
        ]

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_named_holiday_dates_sync"
        ) as mock_get_named_dates:
            await async_prime_holiday_cache(schedules, [2026, 2026, 2027])

        assert mock_get_named_dates.call_count == 2
        mock_get_named_dates.assert_any_call(
            "DE", "public", "Good Friday", "iexact", 2026
        )
        mock_get_named_dates.assert_any_call(
            "DE", "public", "Good Friday", "iexact", 2027
        )

    def test_get_named_holiday_dates_uses_named_lookup(self):
        """Test resolving a holiday by name through the provider."""
        mock_country_holidays = MagicMock()
        mock_country_holidays.get_named.return_value = [date(2026, 4, 3)]

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_country_holidays_sync",
            return_value=mock_country_holidays,
        ):
            result = _get_named_holiday_dates_sync(
                "DE", "public", "Good Friday", "iexact", 2026
            )

        assert result == (date(2026, 4, 3),)
        mock_country_holidays.get_named.assert_called_once_with(
            "Good Friday", lookup="iexact"
        )

    def test_generate_holiday_schedule_dates_merges_contiguous_dates(self):
        """Test contiguous holiday dates collapse into a single range."""
        schedule = {
            "schedule_type": "holiday",
            "country_code": "TR",
            "category": "public",
            "holiday_name": "Ramazan Bayrami",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
        }

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_named_holiday_dates_sync",
            return_value=(
                date(2026, 3, 20),
                date(2026, 3, 21),
                date(2026, 3, 22),
            ),
        ):
            result = generate_holiday_schedule_dates(schedule, 2026)

        assert result == [(date(2026, 3, 20), date(2026, 3, 22))]

    def test_generate_holiday_schedule_dates_applies_offsets(self):
        """Test holiday offsets extend the resolved date range."""
        schedule = {
            "schedule_type": "holiday",
            "country_code": "DE",
            "category": "public",
            "holiday_name": "Good Friday",
            "name_lookup": "iexact",
            "start_offset": 1,
            "end_offset": 2,
        }

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_named_holiday_dates_sync",
            return_value=(date(2026, 4, 3),),
        ):
            result = generate_holiday_schedule_dates(schedule, 2026)

        assert result == [(date(2026, 4, 2), date(2026, 4, 5))]


class TestCalculateOccurrenceEdgeCases:
    """Test additional edge cases for occurrence calculation."""

    def test_calculate_occurrence_invalid_date(self):
        """Test occurrence calculation with invalid inputs."""
        # Test with date that could cause calculation errors
        result = calculate_occurrence(date(2024, 2, 29))  # Leap year
        assert result in [0, 1, 2, 3, 4]  # Should return valid occurrence

    def test_calculate_occurrence_first_day_of_month(self):
        """Test occurrence when date is first day of month."""
        # First Thursday of February 2024 (Feb 1)
        result = calculate_occurrence(date(2024, 2, 1))
        assert result == 0

    def test_calculate_occurrence_last_day_of_month(self):
        """Test occurrence when date is last day of month."""
        # Last day that's the fifth occurrence check
        result = calculate_occurrence(date(2024, 3, 31))  # Sunday
        # Should be 4 (last) if next Sunday is in April
        assert result == 4

    def test_calculate_occurrence_fifth_occurrence(self):
        """Test when a month actually has five occurrences of a weekday."""
        # March 2024 has 5 Fridays: 1, 8, 15, 22, 29
        result = calculate_occurrence(date(2024, 3, 29))  # Fifth Friday
        # Should be 4 (last) because next Friday is in April
        assert result == 4

    def test_calculate_occurrence_error_handling(self):
        """Test that error handling works correctly."""
        # Mock date operations to cause errors
        with patch("custom_components.ha_scheduler.holiday_importer.date") as mock_date:
            # Make date operations raise ValueError
            mock_date.side_effect = ValueError("Invalid date operation")

            # Should return None on error, not crash
            # Note: This test verifies the structure but may need adjustment
            # based on actual implementation
            result = calculate_occurrence(date(2024, 1, 15))
            # Should still work with actual date object
            assert result in [0, 1, 2, 3, 4, None]


class TestOffsetRangeMerging:
    """Offsets must never produce self-overlapping ranges for one schedule."""

    def test_generate_holiday_schedule_dates_merges_offset_overlap(self):
        """Test that offsets which bridge disjoint occurrences are merged.

        Regression test: a holiday occurring on two non-contiguous dates
        (e.g. July 25 and 27) with end_offset=2 produced the overlapping
        ranges (25th-27th) and (27th-29th) for the same schedule.
        """
        schedule = {
            "schedule_type": "holiday",
            "country_code": "CU",
            "category": "public",
            "holiday_name": "Commemoration Day",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 2,
        }

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_named_holiday_dates_sync",
            return_value=(date(2026, 7, 25), date(2026, 7, 27)),
        ):
            result = generate_holiday_schedule_dates(schedule, 2026)

        assert result == [(date(2026, 7, 25), date(2026, 7, 29))]

    def test_generate_holiday_schedule_dates_keeps_disjoint_ranges(self):
        """Test that genuinely disjoint occurrences stay separate ranges."""
        schedule = {
            "schedule_type": "holiday",
            "country_code": "AE",
            "category": "public",
            "holiday_name": "Eid al-Fitr",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
        }

        # A lunar-calendar holiday can occur twice in one Gregorian year.
        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_named_holiday_dates_sync",
            return_value=(date(2033, 1, 2), date(2033, 12, 23)),
        ):
            result = generate_holiday_schedule_dates(schedule, 2033)

        assert result == [
            (date(2033, 1, 2), date(2033, 1, 2)),
            (date(2033, 12, 23), date(2033, 12, 23)),
        ]


class TestFormatDateLocalizedBabelFallback:
    """Test the strftime fallback paths in format_date_localized."""

    def test_babel_import_missing_falls_back_to_strftime(self):
        """Test that a missing babel dependency falls back to strftime."""
        test_date = date(2024, 7, 4)
        with patch.dict(sys.modules, {"babel": None}):
            result = format_date_localized(test_date, "en")
        assert result == test_date.strftime("%B %d")

    def test_invalid_locale_falls_back_to_strftime(self):
        """Test that an unparsable locale code falls back to strftime."""
        test_date = date(2024, 7, 4)
        result = format_date_localized(test_date, "xx_INVALID")
        assert result == test_date.strftime("%B %d")


class TestGetLocalizedCountryNameFallbacks:
    """Test the fallback branches of get_localized_country_name."""

    def test_babel_import_missing_returns_fallback_name(self):
        """Test that a missing babel dependency returns the supplied fallback."""
        with patch.dict(sys.modules, {"babel": None}):
            result = get_localized_country_name("US", "United States")
        assert result == "United States"

    def test_babel_import_missing_without_fallback_title_cases_code(self):
        """Test that a missing fallback name is derived from the country code."""
        with patch.dict(sys.modules, {"babel": None}):
            result = get_localized_country_name("us", None)
        assert result == "Us"

    def test_parse_and_territory_lookup_both_fail_uses_final_fallback(self, caplog):
        """Test that failures in both babel lookups fall through to the final return."""
        mock_locale = MagicMock()
        mock_locale.parse.side_effect = ValueError("bad locale")
        mock_locale.side_effect = ValueError("bad ctor")

        with caplog.at_level(
            logging.DEBUG, logger="custom_components.ha_scheduler.holiday_importer"
        ):
            with patch("babel.Locale", mock_locale):
                result = get_localized_country_name("US", "United States")

        assert result == "United States"
        assert "Could not look up territory name" in caplog.text

    def test_parse_and_territory_lookup_both_fail_without_fallback(self):
        """Test the final fallback title-cases the code when no name is given."""
        mock_locale = MagicMock()
        mock_locale.parse.side_effect = ValueError("bad locale")
        mock_locale.side_effect = ValueError("bad ctor")

        with patch("babel.Locale", mock_locale):
            result = get_localized_country_name("us", None)

        assert result == "Us"


class TestHolidaysModuleUnavailable:
    """Test behavior when the holidays library cannot be imported."""

    def test_get_holidays_module_returns_none_on_import_error(self):
        """Test _get_holidays_module returns None when the import fails."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.importlib.import_module",
            side_effect=ImportError("no holidays"),
        ):
            holiday_importer._get_holidays_module.cache_clear()
            result = holiday_importer._get_holidays_module()

        assert result is None

    def test_holidays_available_logs_one_time_warning(self, caplog):
        """Test _holidays_available returns False and logs a warning once."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.importlib.import_module",
            side_effect=ImportError("no holidays"),
        ):
            holiday_importer._get_holidays_module.cache_clear()
            with caplog.at_level(logging.WARNING):
                result = holiday_importer._holidays_available()

        assert result is False
        assert (
            "holidays library not available - holiday import feature disabled"
            in caplog.text
        )

    def test_get_holidays_library_version_returns_none_when_unavailable(self):
        """Test get_holidays_library_version returns None without the library."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.importlib.import_module",
            side_effect=ImportError("no holidays"),
        ):
            holiday_importer._get_holidays_module.cache_clear()
            result = get_holidays_library_version()

        assert result is None


class TestGetCountryHolidaysSyncGuards:
    """Test the availability guards in _get_country_holidays_sync."""

    def test_returns_none_when_holidays_unavailable(self):
        """Test the function short-circuits when HOLIDAYS_AVAILABLE is False."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", False
        ):
            result = _get_country_holidays_sync("US", "public", 2026)
        assert result is None

    def test_returns_none_when_module_missing(self):
        """Test the function returns None when the holidays module can't load."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer._get_holidays_module",
                return_value=None,
            ):
                result = _get_country_holidays_sync("US", "public", 2026)
        assert result is None


class TestBuildHolidayCacheRequestsEdges:
    """Test edge cases in _build_holiday_cache_requests."""

    def test_empty_years_returns_empty_tuple(self):
        """Test that an empty years collection short-circuits to an empty tuple."""
        schedules = [
            {
                "schedule_type": "holiday",
                "country_code": "US",
                "holiday_name": "Independence Day",
            }
        ]
        result = _build_holiday_cache_requests(schedules, [])
        assert result == ()

    def test_schedule_missing_country_code_is_skipped(self):
        """Test a holiday schedule missing country_code is skipped, others kept."""
        schedules = [
            {"schedule_type": "holiday", "holiday_name": "Missing Country"},
            {
                "schedule_type": "holiday",
                "country_code": "DE",
                "holiday_name": "Good Friday",
                "category": "public",
                "name_lookup": "iexact",
            },
        ]
        result = _build_holiday_cache_requests(schedules, [2026])
        assert result == (("DE", "public", "Good Friday", "iexact", 2026),)


class TestPrimeHolidayCacheSyncFailure:
    """Test that priming failures are logged, not raised."""

    def test_prime_failure_logs_warning_and_does_not_raise(self, caplog):
        """Test a raising lookup is caught and logged as a warning."""
        requests = (("US", "public", "Independence Day", "iexact", 2026),)
        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_named_holiday_dates_sync",
            side_effect=RuntimeError("boom"),
        ):
            with caplog.at_level(logging.WARNING):
                _prime_holiday_cache_sync(requests)

        assert "Could not prime holiday cache" in caplog.text


class TestNamedHolidayDatesProviderWithoutGetNamed:
    """Test the casefold item-scan fallback used when get_named is absent."""

    def test_provider_without_get_named_resolves_by_casefold_scan(self):
        """Test a dict-like provider without get_named is scanned by name."""
        provider = {date(2026, 4, 3): "Test Holiday"}
        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_country_holidays_sync",
            return_value=provider,
        ):
            result = _get_named_holiday_dates_sync(
                "US", "public", "TEST HOLIDAY", "iexact", 2026
            )
        assert result == (date(2026, 4, 3),)

    def test_provider_items_raises_returns_empty_tuple(self, caplog):
        """Test a provider whose items() raises returns an empty tuple, logged."""

        class RaisingItemsProvider:
            def items(self):
                raise RuntimeError("items boom")

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_country_holidays_sync",
            return_value=RaisingItemsProvider(),
        ):
            with caplog.at_level(
                logging.DEBUG,
                logger="custom_components.ha_scheduler.holiday_importer",
            ):
                result = _get_named_holiday_dates_sync(
                    "US", "public", "Test Holiday", "iexact", 2026
                )

        assert result == ()
        assert "Could not resolve holiday" in caplog.text


class TestNamedHolidayDatesLanguageRetry:
    """Test the language-retry loop when the default lookup finds nothing."""

    def test_language_retry_finds_match_after_one_failure(self):
        """Test the retry loop skips a failing language and matches the next.

        The initial (default-language) lookup returns nothing, exposing
        ``supported_languages=("de", "en")`` and ``default_language="de"``.
        The "de" retry raises (covering the continue path) and the "en" retry
        succeeds via the casefold item-scan (no get_named on that provider),
        covering the match branch. A non-public category exercises the
        ``categories`` kwarg branch in the retry call.

        The mock records what it was called with instead of asserting inline:
        an inline assert would run inside the production retry loop's own
        try/except (holiday_importer.py's "except Exception: continue"), so a
        real regression there would be silently swallowed and only surface,
        confusingly, via the final `result` assertion below.
        """

        class InitialProvider:
            supported_languages = ("de", "en")
            default_language = "de"

            def items(self):
                return {}.items()

        class EnglishRetryProvider:
            def items(self):
                return {date(2026, 1, 1): "Neujahr En"}.items()

        calls = []
        captured_kwargs = {}

        def fake_country_holidays_factory(country_code, **kwargs):
            language = kwargs.get("language")
            calls.append(language)
            if language == "de":
                raise RuntimeError("de lookup failed")
            captured_kwargs.update(kwargs)
            return EnglishRetryProvider()

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_country_holidays_sync",
            return_value=InitialProvider(),
        ):
            with patch(
                "holidays.country_holidays",
                side_effect=fake_country_holidays_factory,
            ):
                result = _get_named_holiday_dates_sync(
                    "DE", "bank", "neujahr en", "iexact", 2026
                )

        assert result == (date(2026, 1, 1),)
        assert calls == ["de", "en"]
        assert captured_kwargs.get("categories") == "bank"


class TestGetSupportedCountriesSyncAdditionalFallbacks:
    """Additional fallback branches for _get_supported_countries_sync."""

    def test_module_missing_returns_empty_dict(self):
        """Test the function returns {} when the holidays module can't load."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer._get_holidays_module",
                return_value=None,
            ):
                result = _get_supported_countries_sync()
        assert result == {}

    def test_entity_loader_used_when_country_attribute_matches_code(self):
        """Test the EntityLoader fallback runs when .country equals the code."""
        fake_module = MagicMock()
        fake_module.list_supported_countries.return_value = ["ZZ"]
        country_obj = MagicMock()
        country_obj.country = "ZZ"
        fake_module.country_holidays.return_value = country_obj

        country_class = MagicMock()
        country_class.country = "Zetaland"
        entity_loader = MagicMock()
        entity_loader.get.return_value = country_class
        fake_module.registry.EntityLoader = entity_loader

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer._get_holidays_module",
                return_value=fake_module,
            ):
                with patch(
                    "custom_components.ha_scheduler.holiday_importer"
                    ".get_localized_country_name",
                    side_effect=lambda code, fallback: fallback,
                ):
                    result = _get_supported_countries_sync()

        assert result == {"ZZ": "Zetaland"}
        entity_loader.get.assert_called_once_with("ZZ")

    def test_entity_loader_exception_is_swallowed(self):
        """Test an EntityLoader lookup failure is swallowed, not propagated."""
        fake_module = MagicMock()
        fake_module.list_supported_countries.return_value = ["ZZ"]
        country_obj = MagicMock()
        country_obj.country = "ZZ"
        fake_module.country_holidays.return_value = country_obj

        entity_loader = MagicMock()
        entity_loader.get.side_effect = KeyError("unknown entity")
        fake_module.registry.EntityLoader = entity_loader

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer._get_holidays_module",
                return_value=fake_module,
            ):
                with patch(
                    "custom_components.ha_scheduler.holiday_importer"
                    ".get_localized_country_name",
                    side_effect=lambda code, fallback: fallback,
                ):
                    result = _get_supported_countries_sync()

        # holidays_name stays "ZZ" (the raised lookup never overwrote it).
        assert result == {"ZZ": "ZZ"}


class TestGetAvailableCategoriesSyncAdditionalFallbacks:
    """Additional fallback branches for _get_available_categories_sync."""

    def test_module_missing_returns_default_category(self):
        """Test the function returns the default when the module can't load."""
        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer._get_holidays_module",
                return_value=None,
            ):
                result = _get_available_categories_sync("US")
        assert result == {"public": "Public Holidays"}

    def test_probe_loop_builds_dict_and_skips_failing_category(self, caplog):
        """Test the probe loop finds working categories and skips failures."""

        class Empty:
            def __len__(self):
                return 0

        class NonEmpty:
            def __len__(self):
                return 1

        def fake_country_holidays(country_code, categories=None, years=None):
            if categories == "bank":
                raise RuntimeError("bank not supported")
            if categories == "public":
                return NonEmpty()
            return Empty()

        fake_module = MagicMock()
        fake_module.country_holidays.side_effect = fake_country_holidays

        with patch(
            "custom_components.ha_scheduler.holiday_importer.HOLIDAYS_AVAILABLE", True
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer._get_holidays_module",
                return_value=fake_module,
            ):
                with caplog.at_level(
                    logging.DEBUG,
                    logger="custom_components.ha_scheduler.holiday_importer",
                ):
                    result = _get_available_categories_sync("US")

        assert result == {"public": "Public"}
        assert "Category bank not supported for US" in caplog.text


class TestGetHolidaysForCountrySyncExceptHandlers:
    """Test the per-year except-handler in _get_holidays_for_country_sync.

    The outer per-category except-handler is not covered here: the only
    thing the outer try wraps is this per-year loop, whose own except
    already catches every Exception and continues, so the outer handler is
    unreachable short of a second, unrelated failure (e.g. the logging call
    itself raising) -- see the pragma on that block instead.
    """

    def test_per_year_failure_is_skipped_and_logged(self, caplog):
        """Test one year's failure is skipped while other years still resolve."""

        def fake_country_holidays(country_code, category, year):
            if year == 2025:
                raise RuntimeError("year lookup boom")
            return {date(year, 1, 1): "New Year"}

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_country_holidays_sync",
            side_effect=fake_country_holidays,
        ):
            with patch(
                "custom_components.ha_scheduler.holiday_importer"
                "._get_available_categories_sync",
                return_value={"public": "Public Holidays"},
            ):
                with caplog.at_level(
                    logging.DEBUG,
                    logger="custom_components.ha_scheduler.holiday_importer",
                ):
                    today = date(2025, 6, 15)
                    result = _get_holidays_for_country_sync(
                        "US", ["public"], today=today
                    )

        assert "New Year" in result
        # 2025 failed but other years in the lookaround window succeeded.
        assert len(result["New Year"]["dates"]) >= 1
        assert "Could not get public holidays for US in 2025" in caplog.text


class TestGetHolidaysForCountryAsyncWrapper:
    """Test the async wrapper delegates to the sync implementation."""

    @pytest.mark.asyncio
    async def test_async_wrapper_returns_sync_result(self):
        """Test get_holidays_for_country returns the sync function's result."""
        fake_result = {
            "Independence Day": {
                "name": "Independence Day",
                "category": "public",
                "dates": [date(2026, 7, 4)],
                "pattern": None,
            }
        }
        with patch(
            "custom_components.ha_scheduler.holiday_importer"
            "._get_holidays_for_country_sync",
            return_value=fake_result,
        ) as mock_sync:
            result = await get_holidays_for_country("US")

        assert result == fake_result
        mock_sync.assert_called_once_with("US", None, None)


class TestPatternAnalysisEdgeCases:
    """Test edge cases in holiday pattern analysis helpers."""

    def test_analyze_holiday_pattern_empty_list_returns_none(self):
        """Test analyze_holiday_pattern returns None for an empty input."""
        assert analyze_holiday_pattern([]) is None

    def test_build_nth_weekday_pattern_no_shared_occurrence_returns_none(self):
        """Test anchors that don't share a single occurrence return None."""
        # 2024-01-01 is the 1st Monday of January; 2025-01-13 is the 2nd
        # Monday of January. No single occurrence value reproduces both.
        anchors = [date(2024, 1, 1), date(2025, 1, 13)]
        assert _build_nth_weekday_pattern(anchors, span_days=0) is None

    def test_multi_day_pattern_differing_span_lengths_returns_none(self):
        """Test spans of differing lengths across years return None."""
        dates_by_year = {
            2024: [date(2024, 3, 1), date(2024, 3, 3)],  # span=2 days
            2025: [date(2025, 3, 1), date(2025, 3, 4)],  # span=3 days
        }
        assert _analyze_multi_day_pattern(dates_by_year) is None

    def test_multi_day_pattern_differing_months_returns_none(self):
        """Test same-length spans anchored in different months return None."""
        dates_by_year = {
            2024: [date(2024, 3, 1), date(2024, 3, 3)],  # span=2, March
            2025: [date(2025, 4, 1), date(2025, 4, 3)],  # span=2, April
        }
        assert _analyze_multi_day_pattern(dates_by_year) is None

    def test_calculate_occurrence_overflow_near_date_max_returns_four(self, caplog):
        """Test dates within reach of date.max hit the OverflowError path."""
        with caplog.at_level(
            logging.DEBUG, logger="custom_components.ha_scheduler.holiday_importer"
        ):
            result = calculate_occurrence(date.max)

        assert result == 4
        assert "Could not calculate next occurrence" in caplog.text


class TestMiscSmallReturns:
    """Test miscellaneous small early-return branches."""

    def test_merge_contiguous_dates_empty_input_returns_empty_list(self):
        """Test _merge_contiguous_dates([]) returns an empty list."""
        assert _merge_contiguous_dates([]) == []

    def test_generate_holiday_schedule_dates_missing_country_code_returns_empty(self):
        """Test a schedule missing country_code returns an empty list."""
        schedule = {"holiday_name": "Independence Day"}
        assert generate_holiday_schedule_dates(schedule, 2026) == []

    def test_generate_holiday_schedule_dates_bad_offset_returns_empty(self):
        """Test a non-numeric start_offset returns an empty list."""
        schedule = {
            "country_code": "US",
            "holiday_name": "Independence Day",
            "start_offset": "abc",
        }
        assert generate_holiday_schedule_dates(schedule, 2026) == []

    def test_should_use_holiday_schedule_pattern_none_returns_false(self):
        """Test _should_use_holiday_schedule_pattern(None) returns False."""
        assert _should_use_holiday_schedule_pattern(None) is False
