"""Test the schedule generator."""

from datetime import date

from custom_components.ha_scheduler.schedule_generator import (
    check_overlap,
    generate_schedule_dates,
)


def test_generate_by_date_same_year() -> None:
    """Test generating dates for by_date schedule within same year."""
    schedule = {
        "schedule_type": "date",
        "start_month": 3,
        "start_day": 15,
        "end_month": 6,
        "end_day": 20,
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1
    assert dates[0] == (date(2024, 3, 15), date(2024, 6, 20))


def test_generate_by_date_year_wrap() -> None:
    """Test generating dates for by_date schedule that wraps years."""
    schedule = {
        "schedule_type": "date",
        "start_month": 12,
        "start_day": 15,
        "end_month": 1,
        "end_day": 15,
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1
    assert dates[0] == (date(2024, 12, 15), date(2025, 1, 15))


def test_generate_by_week() -> None:
    """Test generating dates for by_week schedule."""
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 1,  # Second week (has Monday)
        "start_day_of_week": 0,  # Monday
        "end_month": 6,
        "end_week": 4,  # Last week
        "end_day_of_week": 4,  # Friday
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1
    # Monday of second week of March 2024 is March 4
    assert dates[0][0] == date(2024, 3, 4)
    # Friday of last week of June 2024 is June 28
    assert dates[0][1] == date(2024, 6, 28)


def test_generate_by_nth_day() -> None:
    """Test generating dates for by_nth_day schedule."""
    schedule = {
        "schedule_type": "nth-day",
        "month": 3,
        "occurrence": 1,  # Second occurrence
        "day_of_week": 1,  # Tuesday
        "start_offset": 2,
        "end_offset": 3,
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1
    # Second Tuesday of March 2024 is March 12
    # With 2 days before and 3 days after: March 10 to March 15
    assert dates[0] == (date(2024, 3, 10), date(2024, 3, 15))


def test_generate_by_nth_day_last_occurrence() -> None:
    """Test generating dates for last occurrence."""
    schedule = {
        "schedule_type": "nth-day",
        "month": 12,
        "occurrence": 4,  # Last occurrence
        "day_of_week": 4,  # Friday
        "start_offset": 0,
        "end_offset": 0,
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1
    # Last Friday of December 2024 is December 27
    assert dates[0] == (date(2024, 12, 27), date(2024, 12, 27))


def test_generate_by_holiday() -> None:
    """Test generating dates for a holiday-backed schedule."""
    schedule = {
        "schedule_type": "holiday",
        "country_code": "DE",
        "category": "public",
        "holiday_name": "Karfreitag",
        "name_lookup": "iexact",
        "start_offset": 0,
        "end_offset": 0,
    }

    dates = generate_schedule_dates(schedule, 2026)
    assert len(dates) == 1
    assert dates[0] == (date(2026, 4, 3), date(2026, 4, 3))


def test_generate_by_holiday_with_offsets() -> None:
    """Test holiday offsets around the resolved holiday date."""
    schedule = {
        "schedule_type": "holiday",
        "country_code": "DE",
        "category": "public",
        "holiday_name": "Karfreitag",
        "name_lookup": "iexact",
        "start_offset": 1,
        "end_offset": 2,
    }

    dates = generate_schedule_dates(schedule, 2026)
    assert len(dates) == 1
    assert dates[0] == (date(2026, 4, 2), date(2026, 4, 5))


def test_check_overlap_no_overlap() -> None:
    """Test overlap detection with no overlap."""
    schedule1 = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 3,
        "end_day": 31,
        "uid": "schedule1",
    }

    schedule2 = {
        "schedule_type": "date",
        "start_month": 6,
        "start_day": 1,
        "end_month": 8,
        "end_day": 31,
        "uid": "schedule2",
        "name": "Summer",
    }

    has_overlap, name = check_overlap(schedule1, [schedule2])
    assert not has_overlap
    assert name is None


def test_check_overlap_with_overlap() -> None:
    """Test overlap detection with overlap."""
    schedule1 = {
        "schedule_type": "date",
        "start_month": 3,
        "start_day": 1,
        "end_month": 6,
        "end_day": 30,
        "uid": "schedule1",
    }

    schedule2 = {
        "schedule_type": "date",
        "start_month": 5,
        "start_day": 1,
        "end_month": 8,
        "end_day": 31,
        "uid": "schedule2",
        "name": "Overlapping",
    }

    has_overlap, name = check_overlap(schedule1, [schedule2])
    assert has_overlap
    assert name == "Overlapping"


def test_check_overlap_exclude_self() -> None:
    """Test overlap detection excludes self when editing."""
    schedule1 = {
        "schedule_type": "date",
        "start_month": 3,
        "start_day": 1,
        "end_month": 6,
        "end_day": 30,
        "uid": "schedule1",
    }

    # Same schedule but checking against itself
    has_overlap, name = check_overlap(schedule1, [schedule1], exclude_uid="schedule1")
    assert not has_overlap
    assert name is None


def test_check_overlap_year_wrap() -> None:
    """Test overlap detection with year-wrapping schedules."""
    schedule1 = {
        "schedule_type": "date",
        "start_month": 11,
        "start_day": 1,
        "end_month": 2,
        "end_day": 28,
        "uid": "schedule1",
    }

    schedule2 = {
        "schedule_type": "date",
        "start_month": 12,
        "start_day": 15,
        "end_month": 1,
        "end_day": 15,
        "uid": "schedule2",
        "name": "Winter",
    }

    has_overlap, name = check_overlap(schedule1, [schedule2])
    assert has_overlap
    assert name == "Winter"


def test_check_overlap_detects_future_gregorian_cycle_collision() -> None:
    """Test overlap detection catches conflicts beyond the next 3 years."""
    schedule1 = {
        "schedule_type": "date",
        "start_month": 1,
        "start_day": 1,
        "end_month": 1,
        "end_day": 1,
        "uid": "schedule1",
    }

    schedule2 = {
        "schedule_type": "nth-day",
        "month": 1,
        "occurrence": 0,
        "day_of_week": 0,
        "start_offset": 0,
        "end_offset": 0,
        "uid": "schedule2",
        "name": "First Monday of January",
    }

    has_overlap, name = check_overlap(schedule1, [schedule2])
    assert has_overlap
    assert name == "First Monday of January"
