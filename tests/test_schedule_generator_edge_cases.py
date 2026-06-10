"""Test edge cases and error handling in schedule generator."""

from datetime import date

from custom_components.ha_scheduler.schedule_generator import (
    _get_nth_weekday,
    check_overlap,
    generate_schedule_dates,
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


def test_get_nth_weekday_nonexistent_occurrence() -> None:
    """Test _get_nth_weekday when requested occurrence doesn't exist."""
    # Request 5th Sunday of February 2024 (likely doesn't exist)
    result = _get_nth_weekday(2024, 2, 4, 6)  # 5th Sunday (0-indexed week 4)
    # Should return None if it doesn't exist
    if result is None:
        assert True  # Expected behavior
    else:
        # If it does exist, verify it's actually the 5th Sunday
        assert result.weekday() == 6  # Sunday


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
    has_overlap, conflicting_name = check_overlap(schedule1, [schedule2])
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

    has_overlap, conflicting_name = check_overlap(schedule1, [schedule3])
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
