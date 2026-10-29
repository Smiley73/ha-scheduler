"""Constants for the Scheduler integration."""

DOMAIN = "ha_scheduler"

SCHEDULE_TYPE_DATE = "date"
SCHEDULE_TYPE_WEEK = "week"
SCHEDULE_TYPE_NTH_DAY = "nth-day"
SCHEDULE_TYPE_HOLIDAY = "holiday"

# How many years before/after today to include when generating calendar events
CALENDAR_YEAR_LOOKAROUND = 3

# Widest window, in calendar years, that one async_get_events request may span.
# The window is caller-supplied through the calendar REST, websocket and
# service APIs, and every year in it costs holiday-library work, so wider
# requests are rejected instead of iterated.
CALENDAR_MAX_EVENT_SPAN_YEARS = 20

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

# Monday = 0, Sunday = 6
DAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

# Occurrence 4 means "last", not "fifth"
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

# Format: "occurrence_type" where occurrence is 0-4 and type is "partial" or "full"
# For occurrences 1-4 (second, third, fourth, last), type doesn't matter as they're always full weeks
WEEK_OCCURRENCE_OPTIONS = [
    ("0_partial", "first"),
    ("0_full", "first_full"),
    ("1", "second"),
    ("2", "third"),
    ("3", "fourth"),
    ("4", "last"),
]
