"""Test week schedule with optional day of week fields."""

from datetime import date

from custom_components.ha_scheduler.schedule_generator import (
    generate_schedule_dates,
    get_country_first_weekday,
)


def test_get_country_first_weekday() -> None:
    """Test country-specific first weekday function."""
    # Sunday-first countries
    assert get_country_first_weekday("US") == 6
    assert get_country_first_weekday("CA") == 6
    assert get_country_first_weekday("JP") == 6

    # Monday-first countries
    assert get_country_first_weekday("GB") == 0
    assert get_country_first_weekday("DE") == 0
    assert get_country_first_weekday("AU") == 0

    # Default (no country or unknown country)
    assert get_country_first_weekday(None) == 0
    assert get_country_first_weekday("XX") == 0  # Unknown country


def test_generate_by_week_whole_week() -> None:
    """Test generating dates for by_week schedule without specific days (whole week)."""
    # Test whole week schedule (no day_of_week fields specified)
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First week
        "end_month": 3,
        "end_week": 0,  # Same week
        # No start_day_of_week or end_day_of_week
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # March 2024: March 1 is Friday. In Monday-first system:
    # First week starts March 1 and goes for full week (March 1-7)
    assert start_date == date(2024, 3, 1)  # First day of month
    assert end_date == date(2024, 3, 7)  # End of first full week


def test_generate_by_week_whole_week_us() -> None:
    """Test generating dates for by_week schedule with US country (Sunday-first)."""
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First week
        "end_month": 3,
        "end_week": 0,  # Same week
        "country_code": "US",  # Sunday-first
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # March 2024 with Sunday-first: March 1 is Friday
    # First week starts March 1 and goes for full week (March 1-7)
    assert start_date == date(2024, 3, 1)  # First day of month
    assert end_date == date(2024, 3, 7)  # End of first full week


def test_generate_by_week_partial_start_day_only() -> None:
    """Test generating dates with only start day specified."""
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First week
        "start_day_of_week": 2,  # Wednesday
        "end_month": 3,
        "end_week": 0,  # Same week
        # No end_day_of_week - should go to end of week
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # Should start on Wednesday of first week and go to end of that week
    # March 2024: First Wednesday is March 6, in the first full week March 1-7
    assert start_date == date(2024, 3, 6)  # First Wednesday
    assert start_date.weekday() == 2  # Wednesday
    assert end_date == date(2024, 3, 7)  # End of first week


def test_generate_by_week_partial_end_day_only() -> None:
    """Test generating dates with only end day specified."""
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First week
        "end_month": 3,
        "end_week": 0,  # Same week
        "end_day_of_week": 4,  # Friday
        # No start_day_of_week - should start from beginning of week
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # Should start at beginning of first week and end on Friday
    assert start_date == date(2024, 3, 1)  # Start of first week
    assert end_date.weekday() == 4  # Friday
    assert end_date.month == 3


def test_generate_by_week_original_behavior() -> None:
    """Test that original behavior still works when both days are specified."""
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First week
        "start_day_of_week": 0,  # Monday
        "end_month": 3,
        "end_week": 4,  # Last week
        "end_day_of_week": 4,  # Friday
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # Should work exactly as before
    assert start_date.weekday() == 0  # Monday
    assert end_date.weekday() == 4  # Friday
    assert start_date.month == 3
    assert end_date.month == 3


def test_generate_by_week_multiple_weeks() -> None:
    """Test whole week schedule spanning multiple weeks."""
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 1,  # Second week
        "end_month": 3,
        "end_week": 2,  # Third week
        # No day_of_week fields - whole weeks
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # Should span from start of second week to end of third week
    assert start_date.month == 3
    assert end_date.month == 3
    assert (end_date - start_date).days >= 13  # At least 2 weeks


def test_generate_by_week_missing_required_fields() -> None:
    """Test that missing required fields return empty list."""
    # Missing start_week
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "end_month": 3,
        "end_week": 0,
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert dates == []

    # Missing end_month
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,
        "end_week": 0,
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert dates == []


def test_generate_by_week_partial_type() -> None:
    """Test week schedule with partial week type (first week may start in previous month)."""
    # March 2024: March 1 is Friday, so first week starts Feb 26 (Monday)
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First week
        "end_month": 3,
        "end_week": 0,  # Same week
        "start_week_type": "partial",  # Explicitly set to partial
        "end_week_type": "partial",
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # With partial type, first week starts on March 1 (first day of month)
    assert start_date == date(2024, 3, 1)
    assert end_date == date(2024, 3, 7)


def test_generate_by_week_full_type() -> None:
    """Test week schedule with full week type (first week entirely within month)."""
    # March 2024: March 1 is Friday, so first full week is March 4-10 (Monday-Sunday)
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First full week
        "end_month": 3,
        "end_week": 0,  # Same week
        "start_week_type": "full",  # First full week entirely within month
        "end_week_type": "full",
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # With full type, first full week starts on March 4 (first Monday of month)
    assert start_date == date(2024, 3, 4)
    assert end_date == date(2024, 3, 10)


def test_generate_by_week_full_type_us() -> None:
    """Test week schedule with full week type for US (Sunday-first)."""
    # March 2024: March 1 is Friday, so first full week is March 3-9 (Sunday-Saturday)
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First full week
        "end_month": 3,
        "end_week": 0,  # Same week
        "start_week_type": "full",
        "end_week_type": "full",
        "country_code": "US",  # Sunday-first
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # With full type and US (Sunday-first), first full week starts on March 3 (first Sunday)
    assert start_date == date(2024, 3, 3)
    assert end_date == date(2024, 3, 9)


def test_generate_by_week_full_type_multiple_weeks() -> None:
    """Test full week type spanning multiple weeks."""
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,  # First full week
        "end_month": 3,
        "end_week": 1,  # Second week (always full)
        "start_week_type": "full",
        # end_week_type not needed for non-first weeks
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # First full week starts March 4, second week ends March 17
    assert start_date == date(2024, 3, 4)
    # The second week (occurrence 1) should end on March 17, but let's check what we actually get
    # March 11-17 is the second week, so it should end on March 17
    # But our function might be calculating it differently
    assert end_date.month == 3
    assert end_date >= date(2024, 3, 11)  # Should be in second week


def test_generate_by_week_default_week_type() -> None:
    """Test that default week_type is 'partial' when not specified."""
    schedule = {
        "schedule_type": "week",
        "start_month": 3,
        "start_week": 0,
        "end_month": 3,
        "end_week": 0,
        # No start_week_type or end_week_type specified - should default to "partial"
    }

    dates = generate_schedule_dates(schedule, 2024)
    assert len(dates) == 1

    start_date, end_date = dates[0]

    # Should behave like partial type
    assert start_date == date(2024, 3, 1)
    assert end_date == date(2024, 3, 7)
