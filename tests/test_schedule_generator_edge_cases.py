"""Test edge cases and error handling in schedule generator."""

from datetime import date
from unittest.mock import patch

import pytest

from custom_components.ha_scheduler.schedule_generator import (
    _generate_by_date,
    _generate_by_nth_day,
    _generate_by_week,
    _generate_overlap_ranges,
    _get_nth_weekday,
    _get_overlap_years,
    _get_week_end,
    _get_week_start,
    _get_weekday_in_week,
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


def test_generate_by_nth_day_missing_fields_returns_empty() -> None:
    """An nth-day schedule without occurrence and day_of_week yields no dates."""
    schedule = {"schedule_type": "nth-day", "month": 1}

    assert generate_schedule_dates(schedule, 2024) == []


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

    assert generate_schedule_dates(schedule, 2024) == [
        (date(2024, 2, 29), date(2024, 3, 1))
    ]
    # Non-leap year: the start clamps to Feb 28
    assert generate_schedule_dates(schedule, 2023) == [
        (date(2023, 2, 28), date(2023, 3, 1))
    ]


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
def test_get_country_first_weekday_without_babel_locale_data(
    country_code: str, expected: int
) -> None:
    """When Babel can't parse any locale, the fallback table (or its default) is used."""
    with patch("babel.Locale.parse", side_effect=ValueError("no locale data")):
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
    """A day_of_week that can't be coerced to int is swallowed and returns []."""
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


@pytest.mark.parametrize(
    "start_day_of_week, expected_start",
    [
        # Last Wednesday of December 2024.
        (2, date(2024, 12, 25)),
        # No start day: the last week of December 2024 starts on Monday.
        (None, date(2024, 12, 30)),
    ],
)
def test_generate_by_week_year_wrap_with_day_of_week_bounds(
    start_day_of_week: int | None, expected_start: date
) -> None:
    """The end bound of a Dec-to-Jan week schedule lands in the next year."""
    schedule = _week_schedule(
        start_month=12, start_week=4, end_month=1, end_week=0, end_day_of_week=4
    )
    if start_day_of_week is not None:
        schedule["start_day_of_week"] = start_day_of_week

    # Friday of the partial first week of January 2025.
    assert generate_schedule_dates(schedule, 2024) == [
        (expected_start, date(2025, 1, 3))
    ]


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


def _week_schedule(**fields: int | str) -> dict[str, int | str]:
    return {"schedule_type": "week", **fields}


@pytest.mark.parametrize(
    "schedule, expected",
    [
        # Whole week schedule: a range exists in every year of the cycle.
        (_week_schedule(start_month=3, start_week=1, end_month=3, end_week=1), True),
        # Monday-first partial week 0 has no Monday in most years.
        (
            _week_schedule(
                start_month=3,
                start_week=0,
                start_day_of_week=0,
                end_month=3,
                end_week=1,
            ),
            False,
        ),
        # Friday-to-Monday within one week is inverted in every year.
        (
            _week_schedule(
                start_month=3,
                start_week=1,
                start_day_of_week=4,
                end_month=3,
                end_week=1,
                end_day_of_week=0,
            ),
            False,
        ),
    ],
)
def test_week_schedule_has_valid_ranges_requires_range_every_year(
    schedule: dict[str, int | str], expected: bool
) -> None:
    """Only a schedule that yields a range in every year of the cycle is valid."""
    assert week_schedule_has_valid_ranges(schedule) is expected


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
# Overlap cache
# ---------------------------------------------------------------------------


def test_overlap_cache_is_shared_and_keyed_on_date_fields_only() -> None:
    """Validation and overlap checks share one cache entry per equal schedule."""
    schedule = _week_schedule(
        start_month=3,
        start_week=1,
        end_month=3,
        end_week=1,
        country_code="US",
        uid="a",
        name="A",
    )
    _generate_overlap_ranges.cache_clear()

    assert week_schedule_has_valid_ranges(schedule) is True
    info = _generate_overlap_ranges.cache_info()
    assert (info.hits, info.misses) == (0, 1)

    # Same date fields in a different dict, with another uid and name.
    equal = {**schedule, "uid": "b", "name": "B"}
    assert check_overlap(equal, [schedule]) == (True, "A")
    info = _generate_overlap_ranges.cache_info()
    assert (info.hits, info.misses) == (2, 1)

    # country_code is upper-cased in the key.
    check_overlap({**schedule, "country_code": "us"}, [schedule])
    info = _generate_overlap_ranges.cache_info()
    assert (info.hits, info.misses) == (4, 1)

    # A different date field is a different entry.
    check_overlap({**schedule, "start_week": 2, "end_week": 2}, [])
    assert _generate_overlap_ranges.cache_info().misses == 2


def test_check_overlap_compares_typeless_existing_schedule_as_date() -> None:
    """A migrated schedule without schedule_type is compared as a date schedule."""
    new_schedule = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 15,
        "end_month": 1,
        "end_day": 31,
    }
    legacy = {
        "name": "Legacy",
        "start_month": 1,
        "start_day": 10,
        "end_month": 1,
        "end_day": 20,
    }
    assert check_overlap(new_schedule, [legacy]) == (True, "Legacy")
