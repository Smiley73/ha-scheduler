"""Constants for the Scheduler integration."""

DOMAIN = "ha_scheduler"

# How many years before/after today to include when generating calendar events
CALENDAR_YEAR_LOOKAROUND = 3

# Month names for display
MONTH_NAMES = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]

# Day of week names for display (Monday = 0, Sunday = 6)
DAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

# Occurrence names for display (0-4 = first-fifth, but 4 displays as "Last")
OCCURRENCE_NAMES = [
    "first",
    "second",
    "third",
    "fourth",
    "last",
]

# Title-case display variants used in human-readable descriptions and messages.
# MONTH_NAMES_DISPLAY is 1-indexed (index 0 is empty) to allow direct use with
# month integers (1=January … 12=December).
OCCURRENCE_NAMES_DISPLAY = [name.capitalize() for name in OCCURRENCE_NAMES]
DAY_NAMES_DISPLAY = [name.capitalize() for name in DAY_NAMES]
MONTH_NAMES_DISPLAY = [""] + [name.capitalize() for name in MONTH_NAMES]

# Week occurrence options with type support
# Format: "occurrence_type" where occurrence is 0-4 and type is "partial" or "full"
# For occurrences 1-4 (second, third, fourth, last), type doesn't matter as they're always full weeks
WEEK_OCCURRENCE_OPTIONS = [
    ("0_partial", "first"),  # First week (may start in previous month)
    ("0_full", "first_full"),  # First full week (entirely within month)
    ("1", "second"),  # Second week
    ("2", "third"),  # Third week
    ("3", "fourth"),  # Fourth week
    ("4", "last"),  # Last week
]
