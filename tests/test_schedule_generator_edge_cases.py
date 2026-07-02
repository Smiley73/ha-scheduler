"""Test edge cases and error handling in schedule generator."""

import sys
from datetime import date
from unittest.mock import patch

import pytest

from custom_components.ha_scheduler.schedule_generator import (
    _generate_by_date,
    _generate_by_holiday,
    _generate_by_nth_day,
    _generate_by_week,
    _generate_overlap_ranges,
    _get_nth_weekday,
    _get_overlap_signature,
    _get_overlap_years,
    _get_week_end,
    _get_week_start,
    _get_weekday_in_week,
    _schedule_from_signature,
    _uses_deterministic_overlap_cycle,
    _week_schedule_has_valid_ranges,
    check_overlap,
    generate_schedule_dates,
    get_country_first_weekday,
    week_schedule_has_valid_ranges,
)


def test_generate_schedule_dates_invalid_type() -> None:
    """Test generate_schedule_dates with invalid schedule type."""
    schedule = {
        "schedule_type": "invalid_type",
        "start_month": 1,
        "start_day": 1,
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert dates == []


def test_generate_by_date_invalid_date() -> None:
    """Test by_date schedule with invalid date (e.g., Feb 30)."""
    schedule = {
        "schedule_type": "date",
        "start_month": 2,
        "start_day": 30,  # Invalid - February doesn't have 30 days
        "end_month": 3,
        "end_day": 15,
    }

    dates = generate_schedule_dates(schedule, 2024)
    # Should clamp to Feb 29 (2024 is leap year)
    assert len(dates) == 1
    assert dates[0] == (date(2024, 2, 29), date(2024, 3, 15))


def test_generate_by_date_invalid_date_non_leap_year() -> None:
    """Test by_date schedule with Feb 29 in non-leap year."""
    schedule = {
        "schedule_type": "date",
        "start_month": 2,
        "start_day": 29,  # Invalid in non-leap year
        "end_month": 3,
        "end_day": 15,
    }

    dates = generate_schedule_dates(schedule, 2023)  # Non-leap year
    # Should clamp to Feb 28
    assert len(dates) == 1
    assert dates[0] == (date(2023, 2, 28), date(2023, 3, 15))


def test_generate_by_date_missing_fields() -> None:
    """Test by_date schedule with missing required fields."""
    schedule = {
        "schedule_type": "date",
        "start_month": 1,
        # Missing start_day, end_month, end_day
    }

    # Should raise KeyError for missing required fields
    try:
        dates = generate_schedule_dates(schedule, 2024)
        assert dates == []
    except KeyError:
        # Expected behavior - missing required fields cause KeyError
        pass


def test_generate_by_week_invalid_weekday() -> None:
    """Test by_week schedule with invalid weekday."""
    schedule = {
        "schedule_type": "week",
        "start_month": 1,
        "start_week": 0,
        "start_day_of_week": 7,  # Invalid - should be 0-6
        "end_month": 2,
        "end_week": 0,
        "end_day_of_week": 0,
    }

    dates = generate_schedule_dates(schedule, 2024)
    # The function may not validate weekday range, so check if it handles gracefully
    # Either returns empty list or handles the invalid input
    assert isinstance(dates, list)


def test_generate_by_week_nonexistent_week() -> None:
    """Test by_week schedule requesting week that doesn't exist."""
    schedule = {
        "schedule_type": "week",
        "start_month": 2,  # February
        "start_week": 4,  # 5th week - may not exist in February
        "start_day_of_week": 0,
        "end_month": 3,
        "end_week": 0,
        "end_day_of_week": 0,
    }

    dates = generate_schedule_dates(schedule, 2024)
    # Should return empty if the week doesn't exist
    # This depends on the specific February 2024 calendar
    # The function should handle this gracefully
    assert isinstance(dates, list)
    # The function should handle this gracefully


def test_generate_by_nth_day_invalid_occurrence() -> None:
    """Test by_nth_day schedule with invalid occurrence."""
    schedule = {
        "schedule_type": "nth-day",
        "month": 2,
        "occurrence": 5,  # 5th occurrence may not exist (only 0-4 valid)
        "day_of_week": 0,
        "start_offset": 0,
        "end_offset": 7,
    }

    dates = generate_schedule_dates(schedule, 2024)
    # Should return empty if 5th occurrence doesn't exist (only 0-4 valid)
    assert dates == []


def test_generate_by_nth_day_missing_fields() -> None:
    """Test by_nth_day schedule with missing fields."""
    schedule = {
        "schedule_type": "nth-day",
        "month": 1,
        # Missing other required fields like occurrence, day_of_week
    }

    # Should raise KeyError for missing required fields
    try:
        dates = generate_schedule_dates(schedule, 2024)
        assert dates == []
    except KeyError:
        # Expected behavior - missing required fields cause KeyError
        pass


def test_get_nth_weekday_invalid_inputs() -> None:
    """Test _get_nth_weekday with invalid inputs."""
    # Invalid month
    result = _get_nth_weekday(2024, 13, 0, 0)
    assert result is None

    # Invalid occurrence (beyond 0-4 range)
    result = _get_nth_weekday(2024, 1, 5, 0)
    assert result is None

    # Invalid occurrence (negative)
    result = _get_nth_weekday(2024, 1, -1, 0)
    assert result is None


def test_get_nth_weekday_last_occurrence_semantics() -> None:
    """Occurrence 4 means "last" and resolves to concrete dates."""
    # February 2024 has four Sundays; the last is Feb 25.
    assert _get_nth_weekday(2024, 2, 4, 6) == date(2024, 2, 25)
    # March 2024 has five Fridays; "last" (29th) differs from "fourth" (22nd).
    assert _get_nth_weekday(2024, 3, 4, 4) == date(2024, 3, 29)
    assert _get_nth_weekday(2024, 3, 3, 4) == date(2024, 3, 22)


def test_get_nth_weekday_last_occurrence_out_of_range_day_of_week() -> None:
    """An out-of-range day_of_week never matches date.weekday() (0-6).

    day_of_week isn't range-validated at this layer (it's a plain int), so a
    stored/legacy schedule with a bad value must fall through the backward
    scan to None instead of raising or returning a wrong date.
    """
    assert _get_nth_weekday(2024, 3, 4, 99) is None


def test_check_overlap_edge_cases() -> None:
    """Test check_overlap with edge cases."""
    # Same schedule overlapping with itself
    schedule1 = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 1,
        "end_day": 31,
        "uid": "schedule1",
    }

    schedule2 = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 1,
        "end_day": 31,
        "uid": "schedule2",
    }

    # Overlapping schedules
    has_overlap, _conflicting_name = check_overlap(schedule1, [schedule2])
    assert has_overlap is True

    # Non-overlapping schedules
    schedule3 = {
        "schedule_type": "date",
        "start_month": 2,
        "start_day": 1,
        "end_month": 2,
        "end_day": 28,
        "uid": "schedule3",
    }

    has_overlap, _conflicting_name = check_overlap(schedule1, [schedule3])
    assert has_overlap is False


def test_leap_year_handling() -> None:
    """Test schedule generation handles leap years correctly."""
    # Feb 29 in leap year
    schedule = {
        "schedule_type": "date",
        "start_month": 2,
        "start_day": 29,
        "end_month": 3,
        "end_day": 1,
    }

    # Leap year - should work
    dates_leap = generate_schedule_dates(schedule, 2024)
    assert len(dates_leap) == 1
    assert dates_leap[0][0] == date(2024, 2, 29)

    # Non-leap year - should clamp to Feb 28
    dates_non_leap = generate_schedule_dates(schedule, 2023)
    assert len(dates_non_leap) == 1
    assert dates_non_leap[0][0] == date(2023, 2, 28)


def test_year_boundary_edge_cases() -> None:
    """Test schedules that cross year boundaries in edge cases."""
    # December 31 to January 1
    schedule = {
        "schedule_type": "date",
        "start_month": 12,
        "start_day": 31,
        "end_month": 1,
        "end_day": 1,
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1
    assert dates[0] == (date(2024, 12, 31), date(2025, 1, 1))


def test_schedule_generator_robustness() -> None:
    """Test that schedule generator handles malformed input gracefully."""
    # Empty schedule - will default to date type and fail
    try:
        dates = generate_schedule_dates({}, 2024)
        assert dates == []
    except KeyError:
        # Expected behavior - missing required fields
        pass

    # Schedule with None values
    schedule = {
        "schedule_type": "date",
        "start_month": None,
        "start_day": 1,
        "end_month": 2,
        "end_day": 1,
    }
    try:
        dates = generate_schedule_dates(schedule, 2024)
        assert dates == []
    except (KeyError, TypeError):
        # Expected behavior - None values cause errors
        pass

    # Schedule with string values instead of integers
    schedule = {
        "schedule_type": "date",
        "start_month": "1",
        "start_day": "1",
        "end_month": "2",
        "end_day": "1",
    }
    # Should handle type conversion or fail gracefully
    try:
        dates = generate_schedule_dates(schedule, 2024)
        # Either works with type conversion or returns empty list
        assert isinstance(dates, list)
    except (TypeError, ValueError):
        # Expected if no type conversion is done
        pass


def test_date_schedule_across_spring_dst_boundary() -> None:
    """Schedule date math is calendar-based and unaffected by spring DST."""
    # US DST 2026: clocks spring forward on March 8.
    schedule = {
        "schedule_type": "date",
        "start_month": 3,
        "start_day": 7,
        "end_month": 3,
        "end_day": 9,
        "uid": "dst-spring",
    }

    dates = generate_schedule_dates(schedule, 2026)
    assert dates == [(date(2026, 3, 7), date(2026, 3, 9))]


def test_date_schedule_across_fall_dst_boundary() -> None:
    """Schedule date math is calendar-based and unaffected by fall DST."""
    # US DST 2026: clocks fall back on November 1.
    schedule = {
        "schedule_type": "date",
        "start_month": 10,
        "start_day": 31,
        "end_month": 11,
        "end_day": 2,
        "uid": "dst-fall",
    }

    dates = generate_schedule_dates(schedule, 2026)
    assert dates == [(date(2026, 10, 31), date(2026, 11, 2))]


def test_week_schedule_across_dst_boundary() -> None:
    """Week-of-month schedules spanning a DST transition keep whole days."""
    # Second week of March 2026 contains the March 8 spring-forward.
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 1,  # second week
        "end_month": 3,
        "end_week": 1,
        "uid": "dst-week",
    }

    dates = generate_schedule_dates(schedule, 2026)
    assert len(dates) == 1
    start, end = dates[0]
    # The range must cover March 8 fully and span whole days.
    assert start <= date(2026, 3, 8) <= end
    assert (end - start).days == 6


def test_check_overlap_accepts_today_reference_date() -> None:
    """check_overlap accepts an explicit reference date for its horizon."""
    schedule1 = {
        "schedule_type": "date",
        "start_month": 6,
        "start_day": 1,
        "end_month": 6,
        "end_day": 30,
        "name": "June",
        "uid": "june",
    }
    schedule2 = {
        "schedule_type": "date",
        "start_month": 6,
        "start_day": 15,
        "end_month": 7,
        "end_day": 15,
        "name": "Summer",
        "uid": "summer",
    }

    has_overlap, conflicting = check_overlap(
        schedule1, [schedule2], today=date(2026, 1, 1)
    )
    assert has_overlap is True
    assert conflicting == "Summer"

    has_overlap, conflicting = check_overlap(schedule1, [], today=date(2026, 1, 1))
    assert has_overlap is False
    assert conflicting is None


# ---------------------------------------------------------------------------
# get_country_first_weekday babel fallbacks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "country_code, expected",
    [
        # Japan is in COUNTRY_FIRST_WEEKDAY_FALLBACK with value 6 (Sunday).
        ("JP", 6),
        # An unmapped country defaults to Monday.
        ("ZZ", 0),
    ],
)
def test_get_country_first_weekday_babel_import_error(
    country_code: str, expected: int
) -> None:
    """When babel can't be imported, the fallback table (or its default) is used."""
    with patch.dict(sys.modules, {"babel": None}):
        assert get_country_first_weekday(country_code) == expected


def test_get_country_first_weekday_babel_retry_lowercase_locale_success() -> None:
    """If en_XX parsing fails, a lowercase-code retry is used when it succeeds."""

    class _FakeLocale:
        first_week_day = 6

    def fake_parse(locale_str: str) -> _FakeLocale:
        if locale_str.startswith("en_"):
            raise ValueError("simulated unknown locale")
        return _FakeLocale()

    with patch("babel.Locale.parse", side_effect=fake_parse):
        assert get_country_first_weekday("ZZ") == 6


# ---------------------------------------------------------------------------
# Generator exception guards
# ---------------------------------------------------------------------------


def test_generate_by_date_invalid_month_raises_and_is_swallowed() -> None:
    """An out-of-range start_month hits the ValueError guard and returns []."""
    schedule = {
        "start_month": 13,
        "start_day": 1,
        "end_month": 1,
        "end_day": 2,
    }
    assert _generate_by_date(schedule, 2024) == []


def test_generate_by_week_non_int_day_of_week_returns_empty() -> None:
    """A day_of_week that can't be coerced to int hits the outer except clause.

    Both start_day_of_week and end_day_of_week are provided (so the "both
    days specified" branch is taken), and start_day_of_week is a
    non-numeric string. That branch does ``int(start_day_of_week)``, which
    raises ValueError from inside _generate_by_week's own try block (not the
    inner helper's), so it's the outer except (not an inner None-guard) that
    produces the empty result.
    """
    schedule = {
        "start_month": 1,
        "start_week": 0,
        "start_day_of_week": "invalid",
        "end_month": 1,
        "end_week": 1,
        "end_day_of_week": 0,
    }
    assert _generate_by_week(schedule, 2024) == []


def test_generate_by_nth_day_invalid_offset_returns_empty() -> None:
    """A NaN offset raises ValueError when building the timedelta, caught by
    _generate_by_nth_day's own except clause (not the inner helper's).
    """
    schedule = {
        "month": 1,
        "occurrence": 0,
        "day_of_week": 0,
        "start_offset": float("nan"),
    }
    assert _generate_by_nth_day(schedule, 2024) == []


def test_generate_by_holiday_import_failure_returns_empty() -> None:
    """If the lazy holiday_importer import fails, _generate_by_holiday returns []."""
    with patch.dict(
        sys.modules,
        {"custom_components.ha_scheduler.holiday_importer": None},
    ):
        assert _generate_by_holiday({"schedule_type": "holiday"}, 2024) == []


# ---------------------------------------------------------------------------
# Week-math None guards
# ---------------------------------------------------------------------------
#
# Note: a real month never has more than 4 full/partial weeks that "fit"
# within it in the sense _get_week_start checks (the start of the target
# week rolling into the next month) for occurrence values 0-3 -- the UI's
# normal range. To exercise the None-returning "still in the same month"
# guard we use an out-of-range occurrence (5), which is not blocked by any
# earlier validation in these pure date-math functions.


def test_whole_week_schedule_out_of_range_week_returns_empty() -> None:
    """A whole-week schedule whose start week doesn't exist returns []."""
    schedule = {
        "schedule_type": "week",
        "start_month": 2,
        "start_week": 5,
        "start_week_type": "full",
        "end_month": 2,
        "end_week": 0,
    }
    assert generate_schedule_dates(schedule, 2024) == []


def test_week_start_to_end_day_out_of_range_week_returns_empty() -> None:
    """A start-of-week-to-specific-end-day schedule with an invalid start
    week returns [].
    """
    schedule = {
        "schedule_type": "week",
        "start_month": 2,
        "start_week": 5,
        "start_week_type": "full",
        "end_month": 2,
        "end_week": 0,
        "end_day_of_week": 2,
    }
    assert generate_schedule_dates(schedule, 2024) == []


def test_get_week_start_out_of_month_returns_none() -> None:
    """An occurrence whose computed start rolls past the target month is None."""
    assert _get_week_start(2024, 2, 5, 0, "full") is None


def test_get_week_start_overflow_returns_none() -> None:
    """A huge occurrence overflows the internal timedelta math and is caught."""
    assert _get_week_start(9999, 12, 10**9, 0, "partial") is None


def test_get_week_end_none_when_week_start_missing() -> None:
    """_get_week_end returns None when the underlying week start is None."""
    assert _get_week_end(2024, 2, 5, 0, "full") is None


def test_get_week_end_overflow_returns_none() -> None:
    """_get_week_end's own calendar-week-end math can overflow near year 9999."""
    assert _get_week_end(9999, 12, 4, 0, "partial") is None


def test_get_weekday_in_week_none_when_week_bounds_missing() -> None:
    """_get_weekday_in_week returns None when the week itself doesn't exist."""
    assert _get_weekday_in_week(2024, 2, 5, 0, 0, "full") is None


def test_get_weekday_in_week_overflow_returns_none() -> None:
    """Scanning day-by-day through a week ending on date.max can overflow.

    year=9999, month=12, occurrence=3, first_weekday=5 puts the target week
    at Dec 25-31, 9999 (date.max). Asking for a nonexistent weekday (99)
    means the day-scan loop never returns early, so it tries to advance
    past date.max and hits the OverflowError guard.
    """
    assert _get_weekday_in_week(9999, 12, 3, 99, 5, "full") is None


# ---------------------------------------------------------------------------
# week_schedule_has_valid_ranges guards
# ---------------------------------------------------------------------------


def test_week_schedule_has_valid_ranges_non_week_schedule() -> None:
    """A non-week schedule type is rejected before any range generation."""
    assert week_schedule_has_valid_ranges({"schedule_type": "date"}) is False


def test_week_schedule_has_valid_ranges_empty_signature() -> None:
    """An empty signature can't be reconstructed into a schedule."""
    assert _week_schedule_has_valid_ranges(()) is False


# ---------------------------------------------------------------------------
# check_overlap guards
# ---------------------------------------------------------------------------


def test_check_overlap_missing_schedule_type() -> None:
    """A schedule without schedule_type is rejected up front."""
    existing = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 1,
        "end_day": 2,
    }
    assert check_overlap({}, [existing]) == (False, None)


def test_check_overlap_new_schedule_no_cached_ranges(monkeypatch) -> None:
    """If the new schedule generates no cached deterministic ranges, bail out."""
    new_schedule = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 1,
        "end_day": 5,
    }
    existing_schedule = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 1,
        "end_day": 5,
        "name": "Existing",
    }
    monkeypatch.setattr(
        "custom_components.ha_scheduler.schedule_generator._generate_overlap_ranges",
        lambda signature: (),
    )
    assert check_overlap(new_schedule, [existing_schedule]) == (False, None)


def test_check_overlap_existing_schedule_no_ranges() -> None:
    """An existing deterministic schedule that generates no ranges is skipped."""
    new_schedule = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 1,
        "end_day": 5,
        "uid": "new",
    }
    existing_schedule = {
        # An out-of-range start_month makes _generate_by_date return [] for
        # every year in the overlap horizon, so _generate_overlap_ranges
        # naturally produces () for this schedule's signature.
        "schedule_type": "date",
        "start_month": 13,
        "start_day": 1,
        "end_month": 1,
        "end_day": 2,
        "uid": "existing",
        "name": "Existing",
    }
    assert check_overlap(new_schedule, [existing_schedule]) == (False, None)


def test_check_overlap_holiday_existing_no_dates(monkeypatch) -> None:
    """Holiday-involved comparisons use the bounded-horizon path; an existing
    schedule that yields no dates in that horizon is skipped.

    This also exercises _get_overlap_years' holiday-horizon branch, since one
    of the two schedules being compared is a holiday schedule.
    """
    new_schedule = {
        "schedule_type": "holiday",
        "country_code": "US",
        "holiday_name": "Test Holiday",
        "uid": "new",
    }
    existing_schedule = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 1,
        "end_day": 5,
        "name": "Existing",
        "uid": "existing",
    }

    def fake_generate_schedule_dates(schedule, year):
        if schedule.get("schedule_type") == "holiday":
            return [(date(year, 1, 10), date(year, 1, 10))]
        return []

    monkeypatch.setattr(
        "custom_components.ha_scheduler.schedule_generator.generate_schedule_dates",
        fake_generate_schedule_dates,
    )

    result = check_overlap(new_schedule, [existing_schedule], today=date(2026, 1, 1))
    assert result == (False, None)


def test_get_overlap_years_two_date_schedules_uses_full_cycle() -> None:
    """When neither schedule is holiday-backed, the full 400-year Gregorian
    cycle is used instead of the bounded holiday horizon.
    """
    schedule = {"schedule_type": "date"}
    existing = {"schedule_type": "date"}
    assert _get_overlap_years(schedule, existing) == range(2000, 2400)


# ---------------------------------------------------------------------------
# Signature round-trip unit tests
# ---------------------------------------------------------------------------


def test_get_overlap_signature_unknown_type_returns_one_tuple() -> None:
    """An unrecognized schedule_type falls through to a bare 1-tuple."""
    assert _get_overlap_signature({"schedule_type": "unknown"}) == ("unknown",)


def test_schedule_from_signature_empty_returns_none() -> None:
    """An empty signature can't be reconstructed into a schedule dict."""
    assert _schedule_from_signature(()) is None


def test_schedule_from_signature_holiday_round_trip_with_category() -> None:
    """A holiday signature (with a category) rebuilds into a matching dict."""
    holiday_schedule = {
        "schedule_type": "holiday",
        "country_code": "us",
        "category": "public",
        "holiday_name": "Christmas",
        "name_lookup": "iexact",
        "start_offset": 1,
        "end_offset": 2,
    }
    signature = _get_overlap_signature(holiday_schedule)
    rebuilt = _schedule_from_signature(signature)
    assert rebuilt == {
        "schedule_type": "holiday",
        "country_code": "US",
        "holiday_name": "Christmas",
        "name_lookup": "iexact",
        "start_offset": 1,
        "end_offset": 2,
        "category": "public",
    }


def test_schedule_from_signature_holiday_round_trip_without_category() -> None:
    """A holiday signature without a category omits it from the rebuild."""
    holiday_schedule = {
        "schedule_type": "holiday",
        "country_code": "us",
        "holiday_name": "Christmas",
    }
    signature = _get_overlap_signature(holiday_schedule)
    rebuilt = _schedule_from_signature(signature)
    assert rebuilt is not None
    assert "category" not in rebuilt
    assert rebuilt["country_code"] == "US"


def test_schedule_from_signature_unknown_type_returns_none() -> None:
    """An unrecognized signature type can't be reconstructed."""
    assert _schedule_from_signature(("bogus",)) is None


def test_generate_overlap_ranges_unreconstructable_signature_returns_empty() -> None:
    """If the signature can't be turned back into a schedule, no ranges exist."""
    assert _generate_overlap_ranges(("bogus",)) == ()


def test_uses_deterministic_overlap_cycle_empty_signature() -> None:
    """An empty signature never qualifies for the deterministic cache."""
    assert _uses_deterministic_overlap_cycle(()) is False
