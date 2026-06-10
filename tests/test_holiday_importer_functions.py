"""Tests for holiday_importer helper functions."""

import builtins
import importlib
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import custom_components.ha_scheduler.holiday_importer as holiday_importer
from custom_components.ha_scheduler.holiday_importer import (
    _clear_holiday_caches,
    _get_available_categories_sync,
    _get_holidays_for_country_sync,
    _get_named_holiday_dates_sync,
    _get_supported_countries_sync,
    async_prime_holiday_cache,
    calculate_occurrence,
    format_date_localized,
    generate_holiday_schedule_dates,
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
