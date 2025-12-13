"""Constants for the Scheduler integration."""

DOMAIN = "ha_scheduler"

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
