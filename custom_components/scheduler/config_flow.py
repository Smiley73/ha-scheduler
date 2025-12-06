"""Config flow for Scheduler integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import yaml
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TemplateSelectorConfig,
)

from .const import DAY_NAMES, DOMAIN, MONTH_NAMES, OCCURRENCE_NAMES

_LOGGER = logging.getLogger(__name__)


def _get_schedule_type_options(hass: HomeAssistant) -> list[SelectOptionDict]:
    """Get schedule type options with translations."""
    translations = hass.data.get("translations", {})
    component_translations = translations.get(hass.config.language, {}).get(DOMAIN, {})
    selector_translations = (
        component_translations.get("selector", {})
        .get("schedule_type", {})
        .get("options", {})
    )

    return [
        SelectOptionDict(
            value="date", label=selector_translations.get("date", "By Date")
        ),
        SelectOptionDict(
            value="week", label=selector_translations.get("week", "By Week of Month")
        ),
        SelectOptionDict(
            value="nth-day",
            label=selector_translations.get("nth-day", "By Nth Day of Month"),
        ),
    ]


def _get_month_options(hass: HomeAssistant) -> list[SelectOptionDict]:
    """Get month options with translations (values are integers 1-12)."""
    translations = hass.data.get("translations", {})
    component_translations = translations.get(hass.config.language, {}).get(DOMAIN, {})
    selector_translations = (
        component_translations.get("selector", {}).get("month", {}).get("options", {})
    )

    return [
        SelectOptionDict(
            value=str(i + 1),
            label=selector_translations.get(
                MONTH_NAMES[i], MONTH_NAMES[i].capitalize()
            ),
        )
        for i in range(12)
    ]


def _get_day_of_week_options(hass: HomeAssistant) -> list[SelectOptionDict]:
    """Get day of week options with translations (values are integers 0-6)."""
    translations = hass.data.get("translations", {})
    component_translations = translations.get(hass.config.language, {}).get(DOMAIN, {})
    selector_translations = (
        component_translations.get("selector", {})
        .get("day_of_week", {})
        .get("options", {})
    )

    return [
        SelectOptionDict(
            value=str(i),
            label=selector_translations.get(DAY_NAMES[i], DAY_NAMES[i].capitalize()),
        )
        for i in range(7)
    ]


def get_month_selector(hass: HomeAssistant, default: str) -> SelectSelector:
    """Get a month selector with proper labels."""
    return SelectSelector(
        SelectSelectorConfig(
            options=_get_month_options(hass),
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def get_schedule_type_selector(hass: HomeAssistant, default: str) -> SelectSelector:
    """Get a schedule type selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=_get_schedule_type_options(hass),
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def get_day_of_week_selector(hass: HomeAssistant, default: str) -> SelectSelector:
    """Get a day of week selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=_get_day_of_week_options(hass),
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _get_occurrence_options(hass: HomeAssistant) -> list[SelectOptionDict]:
    """Get occurrence options with translations (values are integers 0-4)."""
    translations = hass.data.get("translations", {})
    component_translations = translations.get(hass.config.language, {}).get(DOMAIN, {})
    selector_translations = (
        component_translations.get("selector", {})
        .get("occurrence", {})
        .get("options", {})
    )

    return [
        SelectOptionDict(
            value=str(i),
            label=selector_translations.get(
                OCCURRENCE_NAMES[i], OCCURRENCE_NAMES[i].capitalize()
            ),
        )
        for i in range(5)
    ]


def get_occurrence_selector(hass: HomeAssistant, default: str) -> SelectSelector:
    """Get an occurrence selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=_get_occurrence_options(hass),
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def build_date_config_schema(
    hass: HomeAssistant, defaults: dict[str, Any] | None = None
) -> vol.Schema:
    """Build schema for date-based schedule configuration."""
    if defaults is None:
        defaults = {}

    return vol.Schema(
        {
            # Start configuration
            vol.Required(
                "start_month", default=str(defaults.get("start_month", 1))
            ): get_month_selector(hass, str(defaults.get("start_month", 1))),
            vol.Required(
                "start_day", default=defaults.get("start_day", 1)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=31,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            # End configuration
            vol.Required(
                "end_month", default=str(defaults.get("end_month", 12))
            ): get_month_selector(hass, str(defaults.get("end_month", 12))),
            vol.Required(
                "end_day", default=defaults.get("end_day", 31)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=31,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            # Advanced configuration
            vol.Optional(
                "additional_yaml", default=defaults.get("additional_yaml", "")
            ): TemplateSelector(TemplateSelectorConfig()),
        }
    )


def build_week_config_schema(
    hass: HomeAssistant, defaults: dict[str, Any] | None = None
) -> vol.Schema:
    """Build schema for week-based schedule configuration."""
    if defaults is None:
        defaults = {}

    return vol.Schema(
        {
            # Start configuration
            vol.Required(
                "start_month", default=str(defaults.get("start_month", 1))
            ): get_month_selector(hass, str(defaults.get("start_month", 1))),
            vol.Required(
                "start_week", default=defaults.get("start_week", 0)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=4,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                "start_day_of_week", default=str(defaults.get("start_day_of_week", 0))
            ): get_day_of_week_selector(
                hass, str(defaults.get("start_day_of_week", 0))
            ),
            # End configuration
            vol.Required(
                "end_month", default=str(defaults.get("end_month", 12))
            ): get_month_selector(hass, str(defaults.get("end_month", 12))),
            vol.Required(
                "end_week", default=defaults.get("end_week", 4)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=4,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                "end_day_of_week", default=str(defaults.get("end_day_of_week", 6))
            ): get_day_of_week_selector(hass, str(defaults.get("end_day_of_week", 6))),
            # Advanced configuration
            vol.Optional(
                "additional_yaml", default=defaults.get("additional_yaml", "")
            ): TemplateSelector(TemplateSelectorConfig()),
        }
    )


def build_nth_day_config_schema(
    hass: HomeAssistant, defaults: dict[str, Any] | None = None
) -> vol.Schema:
    """Build schema for nth-day schedule configuration."""
    if defaults is None:
        defaults = {}

    return vol.Schema(
        {
            vol.Required(
                "month", default=str(defaults.get("month", 1))
            ): get_month_selector(hass, str(defaults.get("month", 1))),
            vol.Required(
                "occurrence", default=str(defaults.get("occurrence", 0))
            ): get_occurrence_selector(hass, str(defaults.get("occurrence", 0))),
            vol.Required(
                "day_of_week", default=str(defaults.get("day_of_week", 0))
            ): get_day_of_week_selector(hass, str(defaults.get("day_of_week", 0))),
            vol.Required(
                "start_offset", default=defaults.get("start_offset", 0)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=30,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                "end_offset", default=defaults.get("end_offset", 0)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=30,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                "additional_yaml", default=defaults.get("additional_yaml", "")
            ): TemplateSelector(TemplateSelectorConfig()),
        }
    )


def handle_validation_error(err: ValueError) -> tuple[str, dict[str, str]]:
    """Handle validation errors and return appropriate error key and placeholders."""
    error_msg = str(err)
    error_msg_lower = error_msg.lower()

    if "overlap" in error_msg_lower:
        # Return the full error message as a placeholder
        return "schedule_overlap", {"error_detail": error_msg}
    elif "yaml" in error_msg_lower:
        return "invalid_yaml", {}
    elif "month" in error_msg_lower and "day" not in error_msg_lower:
        return "invalid_month_range", {}
    elif "day of week" in error_msg_lower:
        return "invalid_day_of_week", {}
    elif "week" in error_msg_lower:
        return "invalid_week_range", {}
    elif "day" in error_msg_lower:
        return "invalid_day_range", {}
    else:
        return "invalid_input", {}


def check_date_overlap(
    start_month1: int,
    start_day1: int,
    end_month1: int,
    end_day1: int,
    start_month2: int,
    start_day2: int,
    end_month2: int,
    end_day2: int,
) -> bool:
    """Check if two date ranges overlap."""
    # Convert to comparable format (month * 100 + day)
    start1 = start_month1 * 100 + start_day1
    end1 = end_month1 * 100 + end_day1
    start2 = start_month2 * 100 + start_day2
    end2 = end_month2 * 100 + end_day2

    # Handle wrap-around (e.g., Nov-Feb)
    if start1 > end1:  # Range 1 wraps around year
        if start2 > end2:  # Range 2 also wraps around
            return True  # Both wrap around, they overlap
        else:  # Range 2 doesn't wrap
            # Check if range 2 overlaps with either part of range 1
            return (start2 <= end1) or (end2 >= start1)
    elif start2 > end2:  # Only range 2 wraps around
        # Check if range 1 overlaps with either part of range 2
        return (start1 <= end2) or (end1 >= start2)
    else:  # Neither wraps around
        # Standard overlap check
        return not (end1 < start2 or end2 < start1)


def check_week_overlap(
    start_month1: int,
    start_week1: int,
    start_dow1: int,
    end_month1: int,
    end_week1: int,
    end_dow1: int,
    start_month2: int,
    start_week2: int,
    start_dow2: int,
    end_month2: int,
    end_week2: int,
    end_dow2: int,
) -> bool:
    """Check if two week-based ranges overlap."""
    # Convert to comparable format (month * 1000 + week * 10 + day_of_week)
    start1 = start_month1 * 1000 + start_week1 * 10 + start_dow1
    end1 = end_month1 * 1000 + end_week1 * 10 + end_dow1
    start2 = start_month2 * 1000 + start_week2 * 10 + start_dow2
    end2 = end_month2 * 1000 + end_week2 * 10 + end_dow2

    # Handle wrap-around
    if start1 > end1:  # Range 1 wraps around year
        if start2 > end2:  # Range 2 also wraps around
            return True  # Both wrap around, they overlap
        else:  # Range 2 doesn't wrap
            return (start2 <= end1) or (end2 >= start1)
    elif start2 > end2:  # Only range 2 wraps around
        return (start1 <= end2) or (end1 >= start2)
    else:  # Neither wraps around
        return not (end1 < start2 or end2 < start1)


def check_date_week_overlap(
    date_start_month: int,
    date_start_day: int,
    date_end_month: int,
    date_end_day: int,
    week_start_month: int,
    week_start_week: int,
    week_start_dow: int,
    week_end_month: int,
    week_end_week: int,
    week_end_dow: int,
) -> bool:
    """Check if a date-based range overlaps with a week-based range.

    This is a conservative check - we check if the month ranges overlap.
    Since week-based schedules can span specific weeks within months,
    and date-based schedules span specific days, we check if their
    month ranges overlap as a reasonable approximation.
    """
    # For simplicity, check if the month ranges overlap
    # This is conservative - it may flag some non-overlapping schedules,
    # but it's better to be safe than allow actual overlaps

    date_start = date_start_month * 100 + date_start_day
    date_end = date_end_month * 100 + date_end_day

    # For week-based, use approximate day ranges
    # Week 0 starts around day 1-7, week 1 around 8-14, etc.
    week_start_approx_day = week_start_week * 7 + 1
    week_end_approx_day = min(week_end_week * 7 + 7, 31)

    week_start = week_start_month * 100 + week_start_approx_day
    week_end = week_end_month * 100 + week_end_approx_day

    # Handle wrap-around
    if date_start > date_end:  # Date range wraps around year
        if week_start > week_end:  # Week range also wraps around
            return True  # Both wrap around, they overlap
        else:  # Week range doesn't wrap
            return (week_start <= date_end) or (week_end >= date_start)
    elif week_start > week_end:  # Only week range wraps around
        return (date_start <= week_end) or (date_end >= week_start)
    else:  # Neither wraps around
        return not (date_end < week_start or week_end < date_start)


def calculate_nth_day_range(
    month: int, occurrence: int, day_of_week: int, start_offset: int, end_offset: int
) -> tuple[int, int] | None:
    """Calculate the approximate date range for an nth-day schedule.

    Returns a tuple of (start_day, end_day) for the given month, or None if invalid.
    Uses current year for calculation but returns day numbers only.
    """
    import calendar
    from datetime import datetime

    # Use current year for calculation (doesn't matter which year for day calculation)
    year = datetime.now().year

    # Calculate the target date
    if occurrence == 4:  # Last occurrence
        last_day = calendar.monthrange(year, month)[1]
        for day in range(last_day, 0, -1):
            try:
                check_date = datetime(year, month, day)
                if check_date.weekday() == day_of_week:
                    target_day = day
                    break
            except ValueError:
                continue
        else:
            return None
    else:
        # Find the nth occurrence (0-3)
        count = 0
        target_day = None
        for day in range(1, 32):
            try:
                check_date = datetime(year, month, day)
                if check_date.weekday() == day_of_week:
                    if count == occurrence:
                        target_day = day
                        break
                    count += 1
            except ValueError:
                break

        if target_day is None:
            return None

    # Calculate range with offsets
    start_day = max(1, target_day - start_offset)
    end_day = min(31, target_day + end_offset)

    return (start_day, end_day)


def check_nth_day_overlap(
    month1: int,
    occurrence1: int,
    day_of_week1: int,
    start_offset1: int,
    end_offset1: int,
    month2: int,
    occurrence2: int,
    day_of_week2: int,
    start_offset2: int,
    end_offset2: int,
) -> bool:
    """Check if two nth-day schedules overlap."""
    # If different months, no overlap
    if month1 != month2:
        return False

    # Calculate date ranges for both schedules
    range1 = calculate_nth_day_range(
        month1, occurrence1, day_of_week1, start_offset1, end_offset1
    )
    range2 = calculate_nth_day_range(
        month2, occurrence2, day_of_week2, start_offset2, end_offset2
    )

    if range1 is None or range2 is None:
        return False

    start1, end1 = range1
    start2, end2 = range2

    # Check if ranges overlap
    return not (end1 < start2 or end2 < start1)


def check_nth_day_date_overlap(
    nth_month: int,
    nth_occurrence: int,
    nth_day_of_week: int,
    nth_start_offset: int,
    nth_end_offset: int,
    date_start_month: int,
    date_start_day: int,
    date_end_month: int,
    date_end_day: int,
) -> bool:
    """Check if an nth-day schedule overlaps with a date-based schedule."""
    # Calculate the nth-day range
    nth_range = calculate_nth_day_range(
        nth_month, nth_occurrence, nth_day_of_week, nth_start_offset, nth_end_offset
    )

    if nth_range is None:
        return False

    nth_start_day, nth_end_day = nth_range

    # Check if the nth-day month falls within the date range
    # Handle wrap-around for date ranges
    if date_start_month <= date_end_month:
        # Normal date range (e.g., Jan-Dec)
        if not (date_start_month <= nth_month <= date_end_month):
            return False

        # If in start month, check if nth range starts after date start
        if nth_month == date_start_month and nth_end_day < date_start_day:
            return False

        # If in end month, check if nth range ends before date end
        if nth_month == date_end_month and nth_start_day > date_end_day:
            return False

        return True
    else:
        # Wrap-around date range (e.g., Nov-Feb)
        if not (nth_month >= date_start_month or nth_month <= date_end_month):
            return False

        # If in start month, check if nth range starts after date start
        if nth_month == date_start_month and nth_end_day < date_start_day:
            return False

        # If in end month, check if nth range ends before date end
        if nth_month == date_end_month and nth_start_day > date_end_day:
            return False

        return True


def check_nth_day_week_overlap(
    nth_month: int,
    nth_occurrence: int,
    nth_day_of_week: int,
    nth_start_offset: int,
    nth_end_offset: int,
    week_start_month: int,
    week_start_week: int,
    week_start_dow: int,
    week_end_month: int,
    week_end_week: int,
    week_end_dow: int,
) -> bool:
    """Check if an nth-day schedule overlaps with a week-based schedule."""
    # Calculate the nth-day range
    nth_range = calculate_nth_day_range(
        nth_month, nth_occurrence, nth_day_of_week, nth_start_offset, nth_end_offset
    )

    if nth_range is None:
        return False

    nth_start_day, nth_end_day = nth_range

    # Check if the nth-day month falls within the week range
    # Handle wrap-around for week ranges
    if week_start_month <= week_end_month:
        # Normal week range
        if not (week_start_month <= nth_month <= week_end_month):
            return False
    else:
        # Wrap-around week range
        if not (nth_month >= week_start_month or nth_month <= week_end_month):
            return False

    # Use approximate day ranges for week-based schedule
    week_start_approx_day = week_start_week * 7 + 1
    week_end_approx_day = min(week_end_week * 7 + 7, 31)

    # If in start month, check overlap with week start
    if nth_month == week_start_month:
        if nth_end_day < week_start_approx_day:
            return False

    # If in end month, check overlap with week end
    if nth_month == week_end_month:
        if nth_start_day > week_end_approx_day:
            return False

    return True


async def validate_schedule_input(
    hass: HomeAssistant,
    data: dict[str, Any],
    existing_schedules: dict[str, dict] | None = None,
    current_schedule_id: str | None = None,
) -> dict[str, Any]:
    """Validate the schedule input."""
    # Validate additional_yaml if provided
    additional_yaml = data.get("additional_yaml", "").strip()
    if additional_yaml:
        try:
            parsed_yaml = yaml.safe_load(additional_yaml)
            # Ensure it's a dict or list, not a simple scalar value
            if not isinstance(parsed_yaml, (dict, list)):
                raise ValueError(
                    "YAML must be a dictionary or list structure, not a simple value"
                )
        except yaml.YAMLError as err:
            raise ValueError(f"Invalid YAML: {err}")

    # Validate schedule type specific fields
    schedule_type = data.get("schedule_type", "date")

    # For nth-day schedules, handle month field differently
    if schedule_type == "nth-day":
        month = data.get("month")
        if isinstance(month, str):
            month = int(month)
            data["month"] = month
        if not isinstance(month, int):
            raise ValueError("Month must be an integer")
        if not 1 <= month <= 12:
            raise ValueError("Month must be between 1 and 12")

        # Validate occurrence
        occurrence = data.get("occurrence")
        if isinstance(occurrence, str):
            occurrence = int(occurrence)
            data["occurrence"] = occurrence
        if not isinstance(occurrence, int):
            raise ValueError("Occurrence must be an integer")
        if not 0 <= occurrence <= 4:
            raise ValueError("Occurrence must be between 0 and 4")

        # Validate day_of_week
        day_of_week = data.get("day_of_week")
        if isinstance(day_of_week, str):
            day_of_week = int(day_of_week)
            data["day_of_week"] = day_of_week
        if not isinstance(day_of_week, int):
            raise ValueError("Day of week must be an integer")
        if not 0 <= day_of_week <= 6:
            raise ValueError("Day of week must be between 0 and 6")

        # Validate offsets
        start_offset = data.get("start_offset")
        end_offset = data.get("end_offset")
        if isinstance(start_offset, float):
            start_offset = int(start_offset)
            data["start_offset"] = start_offset
        if isinstance(end_offset, float):
            end_offset = int(end_offset)
            data["end_offset"] = end_offset
        if not isinstance(start_offset, int) or not isinstance(end_offset, int):
            raise ValueError("Offsets must be integers")
        if not 0 <= start_offset <= 30:
            raise ValueError("Start offset must be between 0 and 30")
        if not 0 <= end_offset <= 30:
            raise ValueError("End offset must be between 0 and 30")

        # Remove fields from other schedule types
        data.pop("start_month", None)
        data.pop("end_month", None)
        data.pop("start_day", None)
        data.pop("end_day", None)
        data.pop("start_week", None)
        data.pop("end_week", None)
        data.pop("start_day_of_week", None)
        data.pop("end_day_of_week", None)

        # Check for overlaps with existing schedules
        if existing_schedules:
            for schedule_id, schedule_data in existing_schedules.items():
                # Skip checking against itself when editing
                if current_schedule_id and schedule_id == current_schedule_id:
                    continue

                existing_type = schedule_data.get("schedule_type")

                if existing_type == "nth-day":
                    # Both are nth-day schedules
                    if check_nth_day_overlap(
                        month,
                        occurrence,
                        day_of_week,
                        start_offset,
                        end_offset,
                        schedule_data["month"],
                        schedule_data["occurrence"],
                        schedule_data["day_of_week"],
                        schedule_data["start_offset"],
                        schedule_data["end_offset"],
                    ):
                        raise ValueError(
                            f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                        )
                elif existing_type == "date":
                    # Check nth-day vs date overlap
                    if check_nth_day_date_overlap(
                        month,
                        occurrence,
                        day_of_week,
                        start_offset,
                        end_offset,
                        schedule_data["start_month"],
                        schedule_data["start_day"],
                        schedule_data["end_month"],
                        schedule_data["end_day"],
                    ):
                        raise ValueError(
                            f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                        )
                elif existing_type == "week":
                    # Check nth-day vs week overlap
                    if check_nth_day_week_overlap(
                        month,
                        occurrence,
                        day_of_week,
                        start_offset,
                        end_offset,
                        schedule_data["start_month"],
                        schedule_data["start_week"],
                        schedule_data["start_day_of_week"],
                        schedule_data["end_month"],
                        schedule_data["end_week"],
                        schedule_data["end_day_of_week"],
                    ):
                        raise ValueError(
                            f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                        )

        return {"title": data["name"]}

    # Convert month strings to integers if needed
    start_month = data["start_month"]
    end_month = data["end_month"]

    if isinstance(start_month, str):
        start_month = int(start_month)
        data["start_month"] = start_month
    if isinstance(end_month, str):
        end_month = int(end_month)
        data["end_month"] = end_month

    if not isinstance(start_month, int) or not isinstance(end_month, int):
        raise ValueError("Months must be integers")
    if not 1 <= start_month <= 12:
        raise ValueError("Start month must be between 1 and 12")
    if not 1 <= end_month <= 12:
        raise ValueError("End month must be between 1 and 12")
    # Note: Wrap-around schedules (e.g., Nov-Feb) are supported by overlap checking

    if schedule_type == "date":
        start_day = data.get("start_day")
        end_day = data.get("end_day")

        if start_day is None:
            raise ValueError("Start day must be provided")
        if end_day is None:
            raise ValueError("End day must be provided")

        # Convert to int if it's a float (from NumberSelector)
        if isinstance(start_day, float):
            start_day = int(start_day)
            data["start_day"] = start_day
        if isinstance(end_day, float):
            end_day = int(end_day)
            data["end_day"] = end_day

        if not isinstance(start_day, int) or not isinstance(end_day, int):
            raise ValueError("Days must be numbers")
        if not 1 <= start_day <= 31:
            raise ValueError("Start day must be between 1 and 31")
        if not 1 <= end_day <= 31:
            raise ValueError("End day must be between 1 and 31")
        if start_day > end_day:
            raise ValueError("Start day must be before or equal to end day")

        # Remove week-based fields
        data.pop("start_day_of_week", None)
        data.pop("end_day_of_week", None)
        data.pop("start_week", None)
        data.pop("end_week", None)
    else:  # week
        start_day_of_week = data.get("start_day_of_week")
        end_day_of_week = data.get("end_day_of_week")
        start_week = data.get("start_week")
        end_week = data.get("end_week")

        if start_day_of_week is None:
            raise ValueError("Start day of week must be provided")
        if end_day_of_week is None:
            raise ValueError("End day of week must be provided")
        if start_week is None:
            raise ValueError("Start week must be provided")
        if end_week is None:
            raise ValueError("End week must be provided")

        # Convert day_of_week to int if needed
        if isinstance(start_day_of_week, str):
            start_day_of_week = int(start_day_of_week)
            data["start_day_of_week"] = start_day_of_week
        if isinstance(end_day_of_week, str):
            end_day_of_week = int(end_day_of_week)
            data["end_day_of_week"] = end_day_of_week

        # Convert week to int if needed
        if isinstance(start_week, float):
            start_week = int(start_week)
            data["start_week"] = start_week
        if isinstance(end_week, float):
            end_week = int(end_week)
            data["end_week"] = end_week

        # Validate day_of_week values
        if not isinstance(start_day_of_week, int) or not isinstance(
            end_day_of_week, int
        ):
            raise ValueError("Day of week must be integers")
        if not 0 <= start_day_of_week <= 6:
            raise ValueError("Start day of week must be between 0 and 6")
        if not 0 <= end_day_of_week <= 6:
            raise ValueError("End day of week must be between 0 and 6")

        # Validate week numbers
        if not isinstance(start_week, int) or not isinstance(end_week, int):
            raise ValueError("Week numbers must be integers")
        if not 0 <= start_week <= 4:
            raise ValueError("Start week must be between 0 and 4")
        if not 0 <= end_week <= 4:
            raise ValueError("End week must be between 0 and 4")
        if start_week > end_week:
            raise ValueError("Start week must be before or equal to end week")

        # Remove date-based fields
        data.pop("start_day", None)
        data.pop("end_day", None)

    # Check for overlaps with existing schedules
    if existing_schedules:
        for schedule_id, schedule_data in existing_schedules.items():
            # Skip checking against itself when editing
            if current_schedule_id and schedule_id == current_schedule_id:
                continue

            existing_type = schedule_data.get("schedule_type")

            # Check overlap based on schedule types
            if schedule_type == "date" and existing_type == "date":
                # Both are date-based
                if check_date_overlap(
                    data["start_month"],
                    data["start_day"],
                    data["end_month"],
                    data["end_day"],
                    schedule_data["start_month"],
                    schedule_data["start_day"],
                    schedule_data["end_month"],
                    schedule_data["end_day"],
                ):
                    raise ValueError(
                        f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                    )

            elif schedule_type == "week" and existing_type == "week":
                # Both are week-based
                if check_week_overlap(
                    data["start_month"],
                    data["start_week"],
                    data["start_day_of_week"],
                    data["end_month"],
                    data["end_week"],
                    data["end_day_of_week"],
                    schedule_data["start_month"],
                    schedule_data["start_week"],
                    schedule_data["start_day_of_week"],
                    schedule_data["end_month"],
                    schedule_data["end_week"],
                    schedule_data["end_day_of_week"],
                ):
                    raise ValueError(
                        f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                    )

            elif schedule_type == "date" and existing_type == "week":
                # New is date-based, existing is week-based
                # Convert week-based to approximate date range and check
                if check_date_week_overlap(
                    data["start_month"],
                    data["start_day"],
                    data["end_month"],
                    data["end_day"],
                    schedule_data["start_month"],
                    schedule_data["start_week"],
                    schedule_data["start_day_of_week"],
                    schedule_data["end_month"],
                    schedule_data["end_week"],
                    schedule_data["end_day_of_week"],
                ):
                    raise ValueError(
                        f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                    )

            elif schedule_type == "week" and existing_type == "date":
                # New is week-based, existing is date-based
                # Convert week-based to approximate date range and check
                if check_date_week_overlap(
                    schedule_data["start_month"],
                    schedule_data["start_day"],
                    schedule_data["end_month"],
                    schedule_data["end_day"],
                    data["start_month"],
                    data["start_week"],
                    data["start_day_of_week"],
                    data["end_month"],
                    data["end_week"],
                    data["end_day_of_week"],
                ):
                    raise ValueError(
                        f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                    )

            elif existing_type == "nth-day":
                # Existing is nth-day, new is date or week
                if schedule_type == "date":
                    if check_nth_day_date_overlap(
                        schedule_data["month"],
                        schedule_data["occurrence"],
                        schedule_data["day_of_week"],
                        schedule_data["start_offset"],
                        schedule_data["end_offset"],
                        data["start_month"],
                        data["start_day"],
                        data["end_month"],
                        data["end_day"],
                    ):
                        raise ValueError(
                            f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                        )
                elif schedule_type == "week":
                    if check_nth_day_week_overlap(
                        schedule_data["month"],
                        schedule_data["occurrence"],
                        schedule_data["day_of_week"],
                        schedule_data["start_offset"],
                        schedule_data["end_offset"],
                        data["start_month"],
                        data["start_week"],
                        data["start_day_of_week"],
                        data["end_month"],
                        data["end_week"],
                        data["end_day_of_week"],
                    ):
                        raise ValueError(
                            f"Schedule overlaps with existing schedule '{schedule_data['name']}'"
                        )

    return {"title": data["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Scheduler."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step - create the hub if it doesn't exist."""
        # Check if hub already exists
        existing_entries = self._async_current_entries()
        if existing_entries:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            # Create the hub entry with empty schedules
            return self.async_create_entry(title="Scheduler", data={"schedules": {}})

        # Show a simple confirmation form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": "This will create the Scheduler hub. You can add schedules after setup."
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Scheduler hub - manage schedules."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._schedule_data: dict[str, Any] = {}
        self._schedule_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage schedules."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_schedule",
                "edit_schedule",
                "rename_schedule",
                "remove_schedule",
            ],
        )

    async def async_step_add_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new schedule - name and type selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that name is not "None"
            if user_input.get("name", "").strip().lower() == "none":
                errors["name"] = "invalid_name"
            else:
                self._schedule_data.update(user_input)
                # Generate a unique ID for this schedule
                import uuid

                self._schedule_id = str(uuid.uuid4())

                # Route to the appropriate step based on schedule type
                if user_input["schedule_type"] == "date":
                    return await self.async_step_date_config()
                elif user_input["schedule_type"] == "week":
                    return await self.async_step_week_config()
                else:
                    return await self.async_step_nth_day_config()

        schema = vol.Schema(
            {
                vol.Required("name", default="My Schedule"): str,
                vol.Required(
                    "schedule_type", default="date"
                ): get_schedule_type_selector(self.hass, "date"),
            }
        )

        return self.async_show_form(
            step_id="add_schedule", data_schema=schema, errors=errors
        )

    async def async_step_edit_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a schedule to edit."""
        schedules = self.config_entry.data.get("schedules", {})

        if not schedules:
            return self.async_abort(reason="no_schedules")

        if user_input is not None:
            self._schedule_id = user_input["schedule_id"]
            schedule_data = schedules[self._schedule_id]
            self._schedule_data = dict(schedule_data)

            # Route to the appropriate step based on schedule type
            if schedule_data["schedule_type"] == "date":
                return await self.async_step_date_config()
            elif schedule_data["schedule_type"] == "week":
                return await self.async_step_week_config()
            else:
                return await self.async_step_nth_day_config()

        # Build list of schedules
        schedule_options = [
            SelectOptionDict(value=schedule_id, label=schedule_data["name"])
            for schedule_id, schedule_data in schedules.items()
        ]

        schema = vol.Schema(
            {
                vol.Required("schedule_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=schedule_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="edit_schedule", data_schema=schema)

    async def async_step_rename_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Rename a schedule."""
        schedules = self.config_entry.data.get("schedules", {})

        if not schedules:
            return self.async_abort(reason="no_schedules")

        # If we have a schedule_id stored, show the rename form
        if self._schedule_id and user_input is not None:
            new_name = user_input.get("name", "").strip()

            # Validate that name is not "None"
            if new_name.lower() == "none":
                return self.async_show_form(
                    step_id="rename_schedule",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                "name", default=schedules[self._schedule_id]["name"]
                            ): str,
                        }
                    ),
                    errors={"name": "invalid_name"},
                )

            # Update the schedule name
            new_data = dict(self.config_entry.data)
            new_schedules = dict(new_data.get("schedules", {}))
            new_schedules[self._schedule_id]["name"] = new_name
            new_data["schedules"] = new_schedules

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )

            # Reload the integration to update entities
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        # First step: select which schedule to rename
        if user_input is not None:
            self._schedule_id = user_input["schedule_id"]

            # Show form to enter new name
            schema = vol.Schema(
                {
                    vol.Required(
                        "name", default=schedules[self._schedule_id]["name"]
                    ): str,
                }
            )

            return self.async_show_form(
                step_id="rename_schedule",
                data_schema=schema,
            )

        # Build list of schedules
        schedule_options = [
            SelectOptionDict(value=schedule_id, label=schedule_data["name"])
            for schedule_id, schedule_data in schedules.items()
        ]

        schema = vol.Schema(
            {
                vol.Required("schedule_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=schedule_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="rename_schedule", data_schema=schema)

    async def async_step_remove_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a schedule."""
        schedules = self.config_entry.data.get("schedules", {})

        if not schedules:
            return self.async_abort(reason="no_schedules")

        if user_input is not None:
            schedule_id = user_input["schedule_id"]

            # Remove the schedule
            new_data = dict(self.config_entry.data)
            new_schedules = dict(new_data.get("schedules", {}))
            new_schedules.pop(schedule_id, None)
            new_data["schedules"] = new_schedules

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )

            # Reload the integration to update entities
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        # Build list of schedules
        schedule_options = [
            SelectOptionDict(value=schedule_id, label=schedule_data["name"])
            for schedule_id, schedule_data in schedules.items()
        ]

        schema = vol.Schema(
            {
                vol.Required("schedule_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=schedule_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="remove_schedule", data_schema=schema)

    async def async_step_date_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle date-based schedule configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._schedule_data.update(user_input)
            try:
                # Pass existing schedules for overlap checking
                existing_schedules = self.config_entry.data.get("schedules", {})
                await validate_schedule_input(
                    self.hass,
                    self._schedule_data,
                    existing_schedules,
                    self._schedule_id,  # Pass current schedule ID when editing
                )
            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                # For overlap errors, use the full error message
                if "overlap" in str(err).lower():
                    errors["base"] = str(err)
                else:
                    error_key, _ = handle_validation_error(err)
                    errors["base"] = error_key
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Save the schedule
                new_data = dict(self.config_entry.data)
                new_schedules = dict(new_data.get("schedules", {}))
                new_schedules[self._schedule_id] = self._schedule_data
                new_data["schedules"] = new_schedules

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )

                # Reload the integration to update entities
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        schema = build_date_config_schema(self.hass, self._schedule_data)

        return self.async_show_form(
            step_id="date_config", data_schema=schema, errors=errors
        )

    async def async_step_week_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle week-based schedule configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._schedule_data.update(user_input)
            try:
                # Pass existing schedules for overlap checking
                existing_schedules = self.config_entry.data.get("schedules", {})
                await validate_schedule_input(
                    self.hass,
                    self._schedule_data,
                    existing_schedules,
                    self._schedule_id,  # Pass current schedule ID when editing
                )
            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                # For overlap errors, use the full error message
                if "overlap" in str(err).lower():
                    errors["base"] = str(err)
                else:
                    error_key, _ = handle_validation_error(err)
                    errors["base"] = error_key
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Save the schedule
                new_data = dict(self.config_entry.data)
                new_schedules = dict(new_data.get("schedules", {}))
                new_schedules[self._schedule_id] = self._schedule_data
                new_data["schedules"] = new_schedules

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )

                # Reload the integration to update entities
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        schema = build_week_config_schema(self.hass, self._schedule_data)

        return self.async_show_form(
            step_id="week_config", data_schema=schema, errors=errors
        )

    async def async_step_nth_day_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle nth-day schedule configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._schedule_data.update(user_input)
            try:
                # Pass existing schedules for overlap checking
                existing_schedules = self.config_entry.data.get("schedules", {})
                await validate_schedule_input(
                    self.hass,
                    self._schedule_data,
                    existing_schedules,
                    self._schedule_id,
                )
            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                if "overlap" in str(err).lower():
                    errors["base"] = str(err)
                else:
                    error_key, _ = handle_validation_error(err)
                    errors["base"] = error_key
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Save the schedule
                new_data = dict(self.config_entry.data)
                new_schedules = dict(new_data.get("schedules", {}))
                new_schedules[self._schedule_id] = self._schedule_data
                new_data["schedules"] = new_schedules

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )

                # Reload the integration to update entities
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        schema = build_nth_day_config_schema(self.hass, self._schedule_data)

        return self.async_show_form(
            step_id="nth_day_config", data_schema=schema, errors=errors
        )
