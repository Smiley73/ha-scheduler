"""Tests for holiday_importer helper functions."""

import builtins
import importlib
import logging
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

import custom_components.ha_scheduler.holiday_importer as holiday_importer
from custom_components.ha_scheduler.holiday_importer import (
    _analyze_multi_day_pattern,
    _build_holiday_cache_requests,
    _build_nth_weekday_pattern,
    _get_available_categories_sync,
    _get_country_holidays_sync,
    _get_holidays_for_country_sync,
    _get_named_holiday_dates_sync,
    _get_supported_countries_sync,
    _prime_holiday_cache_sync,
    analyze_holiday_pattern,
    async_prime_holiday_cache,
    format_date_localized,
    generate_holiday_schedule_dates,
    get_holidays_for_country,
    get_holidays_library_version,
    get_localized_country_name,
)
from custom_components.ha_scheduler.schedule_generator import generate_schedule_dates

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@contextmanager
def _patched_holidays_module(module_or_none):
    """Control what _get_holidays_module() resolves to (a fake module or None)."""
    with patch(
        "custom_components.ha_scheduler.holiday_importer._get_holidays_module",
        return_value=module_or_none,
    ):
        yield


@contextmanager
def _holidays_import_fails():
    """Make the real _get_holidays_module() hit its ImportError branch.

    The result is lru_cached, so the cache is cleared on both sides to keep
    the failed import from leaking into later tests.
    """
    with patch(
        "custom_components.ha_scheduler.holiday_importer.importlib.import_module",
        side_effect=ImportError("no holidays"),
    ):
        holiday_importer._get_holidays_module.cache_clear()
        try:
            yield
        finally:
            holiday_importer._get_holidays_module.cache_clear()


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

    assert reloaded_module is not original_module


@pytest.fixture(autouse=True)
def clear_holiday_caches():
    """Reset holiday resolver caches between tests."""
    _get_country_holidays_sync.cache_clear()
    _get_named_holiday_dates_sync.cache_clear()
    yield
    _get_country_holidays_sync.cache_clear()
    _get_named_holiday_dates_sync.cache_clear()


@pytest.mark.parametrize(
    ("test_date", "locale", "expected"),
    [
        (date(2024, 7, 4), "en", "July 4"),
        (date(2024, 12, 25), None, "December 25"),
        (date(2024, 6, 1), None, "June 1"),
    ],
)
def test_format_date_localized(test_date, locale, expected):
    """Dates are formatted as "Month Day" without zero padding, English by default."""
    assert format_date_localized(test_date, locale) == expected


@pytest.mark.parametrize(
    ("country_code", "expected"),
    [
        ("US", "United States"),
        ("CA", "Canada"),
        ("GB", "United Kingdom"),
        ("DE", "Germany"),
    ],
)
def test_get_localized_country_name(country_code, expected):
    """The English territory name comes from Babel, not from the fallback."""
    assert get_localized_country_name(country_code, "unused fallback") == expected


class TestGetSupportedCountriesSync:
    """Test synchronous country discovery."""

    def test_get_supported_countries_success(self):
        """Test getting supported countries."""
        mock_countries = ["US", "CA", "GB"]

        with patch("holidays.list_supported_countries", return_value=mock_countries):
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

    def test_get_supported_countries_error_handling(self):
        """Test error handling in country discovery."""
        mock_countries = ["US", "INVALID"]

        with patch("holidays.list_supported_countries", return_value=mock_countries):
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
        with patch("holidays.list_supported_countries", side_effect=Exception("Error")):
            result = _get_supported_countries_sync()
            # Should return fallback list
            assert isinstance(result, dict)
            # Should have at least some common countries as fallback
            assert len(result) > 0


class TestGetAvailableCategoriesSync:
    """Test synchronous category discovery."""

    def test_get_categories_success(self):
        """Test getting available categories for a country."""
        with patch("holidays.country_holidays") as mock_holidays:
            # Mock successful category tests
            mock_holidays.return_value = MagicMock()

            result = _get_available_categories_sync("US")

            assert isinstance(result, dict)
            # Should at least have public category
            assert "public" in result

    def test_get_categories_error_handling(self):
        """Test error handling in category discovery."""
        with patch("holidays.country_holidays", side_effect=Exception("Error")):
            result = _get_available_categories_sync("INVALID")
            # Should return default public category
            assert result == {"public": "Public Holidays"}


class TestGetHolidaysForCountrySync:
    """Test synchronous holiday retrieval."""

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
        with _patched_holidays_module(None):
            result = _get_holidays_for_country_sync("US")
            assert result == {}

    def test_get_holidays_total_failure(self):
        """Test total failure in holiday retrieval."""
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


@pytest.mark.parametrize(
    ("end_offset", "resolved", "expected"),
    [
        pytest.param(
            0,
            (date(2026, 3, 20), date(2026, 3, 21), date(2026, 3, 22)),
            [(date(2026, 3, 20), date(2026, 3, 22))],
            id="contiguous-dates",
        ),
        # Regression: a holiday on two non-contiguous dates with end_offset=2
        # produced the overlapping ranges (25th-27th) and (27th-29th).
        pytest.param(
            2,
            (date(2026, 7, 25), date(2026, 7, 27)),
            [(date(2026, 7, 25), date(2026, 7, 29))],
            id="offsets-bridge-disjoint-dates",
        ),
    ],
)
def test_generate_holiday_schedule_dates_merges_into_one_range(
    end_offset, resolved, expected
):
    """Contiguous or offset-bridged holiday dates collapse into a single range."""
    schedule = {
        "schedule_type": "holiday",
        "country_code": "US",
        "category": "public",
        "holiday_name": "Test Holiday",
        "name_lookup": "iexact",
        "start_offset": 0,
        "end_offset": end_offset,
    }

    with patch(
        "custom_components.ha_scheduler.holiday_importer._get_named_holiday_dates_sync",
        return_value=resolved,
    ):
        result = generate_holiday_schedule_dates(schedule, 2026)

    assert result == expected


class TestOffsetRangeMerging:
    """Offsets must never produce self-overlapping ranges for one schedule."""

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

    def test_invalid_locale_falls_back_to_strftime(self):
        """Test that an unparsable locale code falls back to strftime."""
        test_date = date(2024, 7, 4)
        result = format_date_localized(test_date, "xx_INVALID")
        assert result == test_date.strftime("%B %d")


class TestGetLocalizedCountryNameFallbacks:
    """Test the fallback branches of get_localized_country_name."""

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

    def test_get_holidays_module_returns_none_on_import_error(self, caplog):
        """Test _get_holidays_module returns None and warns once on ImportError."""
        with _holidays_import_fails():
            with caplog.at_level(logging.WARNING):
                result = holiday_importer._get_holidays_module()
                holiday_importer._get_holidays_module()

        assert result is None
        assert (
            caplog.text.count(
                "holidays library not available - holiday import feature disabled"
            )
            == 1
        )

    def test_get_holidays_library_version_returns_none_when_unavailable(self):
        """Test get_holidays_library_version returns None without the library."""
        with _holidays_import_fails():
            result = get_holidays_library_version()

        assert result is None


class TestGetCountryHolidaysSyncGuards:
    """Test the availability guards in _get_country_holidays_sync."""

    def test_returns_none_when_module_missing(self):
        """Test the function returns None when the holidays module can't load."""
        with _patched_holidays_module(None):
            result = _get_country_holidays_sync("US", "public", 2026)
        assert result is None


class TestBuildHolidayCacheRequestsEdges:
    """Test edge cases in _build_holiday_cache_requests."""

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


class TestNamedHolidayDatesProviderErrors:
    """Test a provider whose lookup raises."""

    def test_provider_get_named_raises_returns_empty_tuple(self, caplog):
        """Test a provider whose get_named() raises returns an empty tuple, logged."""

        class RaisingProvider:
            def get_named(self, holiday_name, lookup):
                raise RuntimeError("get_named boom")

        with patch(
            "custom_components.ha_scheduler.holiday_importer._get_country_holidays_sync",
            return_value=RaisingProvider(),
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
        succeeds, covering the match branch. A non-public category exercises the
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

            def get_named(self, holiday_name, lookup):
                return []

        class EnglishRetryProvider:
            def get_named(self, holiday_name, lookup):
                return [date(2026, 1, 1)]

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
        with _patched_holidays_module(None):
            result = _get_supported_countries_sync()
        assert result == {}


class TestGetAvailableCategoriesSyncAdditionalFallbacks:
    """Additional fallback branches for _get_available_categories_sync."""

    def test_module_missing_returns_default_category(self):
        """Test the function returns the default when the module can't load."""
        with _patched_holidays_module(None):
            result = _get_available_categories_sync("US")
        assert result == {"public": "Public Holidays"}


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


class TestPatternAnalysis:
    """Test holiday pattern analysis and its helpers."""

    def test_analyze_holiday_pattern_empty_list_returns_none(self):
        """Test analyze_holiday_pattern returns None for an empty input."""
        assert analyze_holiday_pattern([]) is None

    def test_analyze_nth_day_pattern(self):
        """Last Monday of May across years is an nth-day pattern with occurrence 4."""
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

    def test_analyze_nth_day_occurrence_validated_across_years(self):
        """Occurrence detection must agree with every analyzed year.

        Regression test: the occurrence used to be computed from the first
        year alone. April 2023's 4th Friday is also its last Friday, so a
        genuine "4th Friday" holiday was misdetected as "Last Friday" and
        generated the wrong date in five-Friday years like 2027.
        """
        dates = [
            date(2023, 4, 28),  # 4th Friday (April 2023 has only 4 Fridays)
            date(2024, 4, 26),
            date(2025, 4, 25),
            date(2026, 4, 24),
            date(2027, 4, 23),  # 4th Friday; last Friday is April 30
        ]

        pattern = analyze_holiday_pattern(list(dates))

        assert pattern is not None
        assert pattern["schedule_type"] == "nth-day"
        assert pattern["occurrence"] == 3  # Fourth, not last
        for expected in dates:
            assert generate_schedule_dates(pattern, expected.year) == [
                (expected, expected)
            ]

    def test_analyze_multi_day_span_generates_input_dates(self):
        """The detected pattern must regenerate the analyzed dates.

        Regression test: the former week-based pattern stored weekday
        occurrences as calendar-week numbers, so a first-Monday/Tuesday
        holiday generated events only in years where the month started on
        a Monday (one in seven) — including none of the analyzed years.
        """
        dates = []
        for year in range(2023, 2030):
            # First Monday of November plus the following Tuesday
            first_monday = next(
                date(year, 11, day)
                for day in range(1, 8)
                if date(year, 11, day).weekday() == 0
            )
            dates.extend([first_monday, first_monday + timedelta(days=1)])

        pattern = analyze_holiday_pattern(list(dates))

        assert pattern is not None
        assert pattern["schedule_type"] == "nth-day"
        assert pattern["month"] == 11
        assert pattern["occurrence"] == 0
        assert pattern["day_of_week"] == 0
        assert pattern["end_offset"] == 1

        # Every analyzed year must be covered by the generated ranges.
        for year in range(2023, 2030):
            ranges = generate_schedule_dates(pattern, year)
            assert len(ranges) == 1, f"no range generated for {year}"
            start, end = ranges[0]
            year_dates = [d for d in dates if d.year == year]
            assert start == year_dates[0]
            assert end == year_dates[-1]

    def test_analyze_multi_day_span_inconsistent(self):
        """Test that inconsistent patterns return None (variable date)."""
        # Dates that don't follow a consistent pattern across years
        dates = [
            date(2023, 3, 6),  # Monday, first week of March 2023
            date(2023, 3, 7),  # Tuesday
            date(2024, 3, 15),  # Different week in 2024
            date(2024, 3, 16),  # Different week in 2024
        ]

        pattern = analyze_holiday_pattern(dates)
        assert pattern is not None
        assert pattern["schedule_type"] == "date"
        assert pattern.get("variable_date") is True

    def test_analyze_multi_day_span_single_year_falls_back(self):
        """A single year of multi-day data cannot establish a recurrence."""
        dates = [date(2023, 3, 6), date(2023, 3, 7)]
        pattern = analyze_holiday_pattern(dates)
        assert pattern is not None
        assert pattern["schedule_type"] == "date"
        assert pattern.get("variable_date") is True

    def test_analyze_holiday_pattern_repeated_july_fourth_is_fixed_date(self):
        """July 4 across several years yields the fixed-date dict."""
        dates = [date(2025, 7, 4), date(2023, 7, 4), date(2024, 7, 4)]
        assert analyze_holiday_pattern(dates) == {
            "schedule_type": "date",
            "start_month": 7,
            "start_day": 4,
            "end_month": 7,
            "end_day": 4,
            "description": "Fixed date: July 4",
        }

    def test_analyze_holiday_pattern_unrecognised_dates_are_variable_date(self):
        """Dates without a recurrence keep variable_date and the first-year description."""
        dates = [date(2024, 5, 22), date(2023, 3, 15), date(2025, 8, 10)]
        assert analyze_holiday_pattern(dates) == {
            "schedule_type": "date",
            "start_month": 3,
            "start_day": 15,
            "end_month": 3,
            "end_day": 15,
            "variable_date": True,
            "description": "Variable date (using 2023 date: March 15)",
        }

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


class TestMiscSmallReturns:
    """Test miscellaneous small early-return branches."""

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
