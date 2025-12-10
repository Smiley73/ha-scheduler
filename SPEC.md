# Home Assistant Scheduler Integration - Specification

**Objective**: Create a Home Assistant custom integration called "Scheduler" that allows users to create recurring annual calendar schedules with flexible date patterns and optional YAML configuration.

## Overview

This integration provides a calendar-based scheduling system where:
- Users can create multiple scheduler instances (each is a separate config entry)
- Each scheduler has its own calendar entity
- Schedules are all-day events that recur annually
- Three scheduling patterns are supported: by date, by week of month, and by nth day of month
- Each schedule can have optional YAML configuration attached

## Core Features

### Multiple Schedulers
- Users can add multiple independent schedulers
- Each scheduler is a separate config entry with its own calendar entity
- Schedulers can be named during setup (must be unique, case-insensitive)

### Schedule Types

#### 1. By Date Schedule
Define a schedule using specific calendar dates that repeat annually.

**User Input**:
- Start month (dropdown: January-December, stored as 1-12)
- Start day (number: 1-31)
- End month (dropdown: January-December, stored as 1-12)
- End day (number: 1-31)

**Behavior**:
- Same dates every year (e.g., March 15 to June 20)
- Handles year wrapping (e.g., December 15 to January 15 of next year)

**Example**: Summer vacation from June 1 to August 31

#### 2. By Week of Month Schedule
Define a schedule using week occurrences within months.

**User Input**:
- Start month (dropdown: January-December, stored as 1-12)
- Start week (dropdown: First/Second/Third/Fourth/Last, stored as 0-4)
- Start day of week (dropdown: Monday-Sunday, stored as 0-6 where 0=Monday)
- End month (dropdown: January-December, stored as 1-12)
- End week (dropdown: First/Second/Third/Fourth/Last, stored as 0-4)
- End day of week (dropdown: Monday-Sunday, stored as 0-6)

**Behavior**:
- Dates vary each year based on calendar
- Only wraps to next year if end month < start month
- Week 4 (Last) means the last occurrence of that weekday in the month

**Example**: First Monday of March to Last Friday of June

#### 3. By Nth Day of Month Schedule
Define a schedule centered on a specific weekday occurrence with offset days.

**User Input**:
- Month (dropdown: January-December, stored as 1-12)
- Occurrence (dropdown: First/Second/Third/Fourth/Last, stored as 0-4)
- Day of week (dropdown: Monday-Sunday, stored as 0-6)
- Days before (number: 0-30) - start offset
- Days after (number: 0-30) - end offset

**Behavior**:
- Finds the nth occurrence of the specified weekday
- Creates event starting N days before and ending M days after
- Dates vary each year based on calendar

**Example**: Second Tuesday of March, 2 days before to 3 days after

### Configuration System

#### Default Configuration
- Each scheduler can have a default YAML configuration
- Accessed via "Default configuration" option in the options menu
- Stored in `config_entry.options["configuration"]`
- Exposed as calendar entity attribute `default_configuration`
- Used when a schedule doesn't have its own configuration

#### Per-Schedule Configuration
- Each schedule can have its own YAML configuration
- Overrides the default configuration when present
- Shown on the same form as schedule parameters
- Stored in schedule dict as `configuration` key
- Exposed in CalendarEvent.description field as a dict (not string)
- Optional - if not provided, uses default configuration

**Configuration Field Requirements**:
- Must be valid YAML syntax
- Must be a structure (dict/list), not a simple string value
- Empty/whitespace-only input removes the configuration
- Field uses `default` parameter to display existing YAML
- Include helper text: "To clear the configuration field, enter a single space character"

## User Interface Flow

### Initial Setup (Config Flow)
1. User initiates integration setup
2. Prompt for scheduler name (default: "Scheduler")
3. Validate name is unique across all schedulers (case-insensitive)
4. Create config entry with empty schedules list

### Options Flow - Main Menu
Present menu with four options:
- Add schedule
- Edit schedule
- Remove schedule
- Default configuration

### Add Schedule Flow
1. **Step 1**: Select schedule type
   - Radio/dropdown: By Date, By Week of Month, By Nth Day of Month
   
2. **Step 2**: Single-page form with all parameters
   - Schedule name (text input, required)
   - All schedule-specific parameters (dates/weeks/occurrences)
   - Configuration (YAML, optional, TemplateSelector)
   - Validate all inputs on this page
   - Show errors inline if validation fails
   
3. **On Submit**:
   - Generate unique UID using `str(uuid.uuid4())`
   - Validate schedule name is unique within this scheduler (case-insensitive)
   - Check for overlaps with existing schedules
   - Add to `config_entry.options["schedules"]` list
   - Preserve all existing schedules

### Edit Schedule Flow
1. **Step 1**: Select schedule from dropdown (shows schedule names)
   
2. **Step 2**: Single-page form with all parameters pre-filled
   - Load schedule data
   - **Critical**: Convert configuration dict to YAML string using `yaml.dump(default_flow_style=False, sort_keys=False)`
   - Display all fields with current values
   - Configuration field uses `default` parameter (not `suggested_value`) to show existing YAML
   - Allow editing all parameters including name
   - Validate on submit
   
3. **On Submit**:
   - Allow keeping same name (exclude current schedule from uniqueness check)
   - Check for overlaps (exclude current schedule)
   - Update schedule in `config_entry.options["schedules"]` list
   - Preserve all other schedules

### Remove Schedule Flow
1. **Step 1**: Select schedule from dropdown (shows schedule names)
   
2. **Step 2**: Confirmation dialog
   - Show schedule name and type
   - Checkbox: "Confirm removal"
   - Only proceed if checkbox is checked
   
3. **On Confirm**:
   - Remove schedule from `config_entry.options["schedules"]` list
   - Preserve all other schedules

### Default Configuration Flow
1. Single-page form with YAML input (TemplateSelector)
2. Pre-fill with current default configuration if exists
3. Validate YAML syntax and structure
4. Save to `config_entry.options["configuration"]`

## Validation Rules

### Schedule Parameters
- Days: Must be 1-31 (will be clamped to valid days for the month)
- Offsets: Must be 0-30
- For by_date: End date must be after start date (considering year wrapping)
- For by_week and by_nth_day: End can be before start in same year

### Name Uniqueness
- **Scheduler names**: Must be unique across all schedulers (case-insensitive)
  - Error: "Name already exists. Please choose a different name."
  
- **Schedule names**: Must be unique within each scheduler (case-insensitive)
  - Error: "A schedule with this name already exists. Please choose a different name."
  - When editing: Allow keeping the same name (exclude current schedule from check)

### Overlap Detection
- Check if new/edited schedule overlaps with existing schedules
- Check across 3 years (current year + 2 more)
- Return tuple: `(has_overlap: bool, conflicting_schedule_name: str | None)`
- Error: "This schedule overlaps with '{conflicting_schedule}'"
- When editing: Exclude current schedule from overlap check

### YAML Configuration Validation
- Must be valid YAML syntax
- Must parse to a dict or list (not a simple string/number)
- Empty string or whitespace-only is valid (removes configuration)
- Error messages should be descriptive (e.g., "Invalid YAML: {error}")

## Data Storage

### Config Entry Structure
```python
{
    "data": {},  # Empty - all data in options
    "options": {
        "schedules": [
            {
                "uid": "uuid-string",
                "name": "Schedule Name",
                "schedule_type": "date",  # or "week", "nth-day"
                
                # For schedule_type="date":
                "start_month": 3,      # 1-12
                "start_day": 15,       # 1-31
                "end_month": 6,        # 1-12
                "end_day": 20,         # 1-31
                
                # For schedule_type="week":
                "start_month": 3,           # 1-12
                "start_week": 0,            # 0-4 (0=first, 4=last)
                "start_day_of_week": 0,     # 0-6 (0=Monday)
                "end_month": 6,             # 1-12
                "end_week": 4,              # 0-4
                "end_day_of_week": 4,       # 0-6
                
                # For schedule_type="nth-day":
                "month": 3,            # 1-12
                "occurrence": 1,       # 0-4 (0=first, 4=last)
                "day_of_week": 1,      # 0-6 (0=Monday)
                "start_offset": 2,     # days before (0-30)
                "end_offset": 3,       # days after (0-30)
                
                # Optional for all types:
                "configuration": {"key": "value"}  # dict or omitted
            }
        ],
        "configuration": {"default": "config"}  # dict or omitted
    }
}
```

### Field Naming Conventions
- Schedule type field: `schedule_type` (values: "date", "week", "nth-day")
- Offset fields: `start_offset`, `end_offset` (not "days_before"/"days_after")
- Week occurrence: `start_week`, `end_week` (0-4)
- Occurrence: `occurrence` (0-4 where 0=first, 4=last)
- Day of week: `day_of_week`, `start_day_of_week`, `end_day_of_week` (0-6 where 0=Monday)
- Months: 1-12 (1=January, 12=December)

## Calendar Entity Implementation

### Event Generation
- Generate events for requested date range
- Include previous year to catch year-wrapping schedules
- Each event has unique UID: `{schedule_uid}_{year}`
- All events are all-day events
- End date is exclusive (add 1 day for calendar display)

### Event Properties
- **summary**: Schedule name
- **start**: Start date (date object, not datetime)
- **end**: End date + 1 day (for all-day event display)
- **description**: Configuration dict (not string) - schedule-specific or default
- **uid**: `{schedule_uid}_{year}`

### Entity Attributes
- `default_configuration`: The scheduler's default YAML configuration dict
- `description`: When a schedule is active, contains the configuration dict for that schedule

### Update Handling
- Listen for config entry options changes
- Regenerate events when schedules are added/edited/removed
- Update calendar entity state

## Implementation Details

### File Structure
```
custom_components/scheduler/
├── __init__.py                 # Setup/unload entry points
├── manifest.json              # Integration metadata
├── const.py                   # Constants (DOMAIN, month/day/occurrence names)
├── config_flow.py             # Config and options flows
├── calendar.py                # Calendar entity implementation
├── schedule_generator.py      # Date calculation logic
├── diagnostics.py             # Diagnostics data collection
├── strings.json              # UI text and translations
└── translations/
    └── en.json               # English translations
```

### const.py
Define constants:
```python
DOMAIN = "scheduler"

MONTH_NAMES = ["january", "february", "march", ...]  # 12 items
DAY_NAMES = ["monday", "tuesday", "wednesday", ...]  # 7 items
OCCURRENCE_NAMES = ["first", "second", "third", "fourth", "last"]  # 5 items
```

### diagnostics.py
Implement diagnostics data collection:

**`async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]`**
- Collect diagnostic information for troubleshooting
- Include entry metadata (title, entry_id)
- Include schedule count and detailed schedule information
- Include schedule-specific fields based on type (date, week, nth-day)
- Include configuration data (both schedule-specific and default)
- Never expose sensitive data (no passwords, tokens, or coordinates)

**Diagnostic Data Structure**:
```python
{
    "entry": {
        "title": "Scheduler Name",
        "entry_id": "config_entry_id"
    },
    "schedules": {
        "count": 2,
        "items": [
            {
                "id": "schedule_uid",
                "name": "Schedule Name",
                "type": "date",  # or "week", "nth-day"
                # Type-specific fields
                "start_month": 6,
                "start_day": 1,
                # ...
                "has_configuration": True,
                "configuration": {"key": "value"}  # if present
            }
        ]
    },
    "default_configuration": {
        "has_default": True,
        "configuration": {"default": "config"}  # if present
    }
}
```

### schedule_generator.py
Implement functions:

**`generate_schedule_dates(schedule: dict, year: int) -> list[tuple[date, date]]`**
- Main entry point for date generation
- Dispatches to type-specific functions
- Returns list of (start_date, end_date) tuples for the year

**`_generate_by_date(schedule: dict, year: int) -> list[tuple[date, date]]`**
- Handle date-based schedules
- Handle year wrapping when end_month < start_month
- Clamp days to valid range for each month

**`_generate_by_week(schedule: dict, year: int) -> list[tuple[date, date]]`**
- Handle week-based schedules
- Find nth occurrence of weekday in month
- Only wrap to next year if end_month < start_month

**`_generate_by_nth_day(schedule: dict, year: int) -> list[tuple[date, date]]`**
- Handle nth-day schedules
- Find nth occurrence of weekday in month
- Apply start_offset (days before) and end_offset (days after)

**`_get_nth_weekday(year: int, month: int, occurrence: int, day_of_week: int) -> date`**
- Find the nth occurrence (0-3) or last (4) of a weekday in a month
- Return the date of that occurrence

**`check_overlap(new_schedule: dict, existing_schedules: list[dict], exclude_uid: str | None = None) -> tuple[bool, str | None]`**
- Check if new_schedule overlaps with any existing schedules
- Check across 3 years (current + 2 more)
- Exclude schedule with exclude_uid from check (for editing)
- Return (has_overlap, conflicting_schedule_name)

### config_flow.py

**Critical Implementation Requirements**:

1. **Always use fresh options data**:
   ```python
   entry = self.hass.config_entries.async_get_entry(self.config_entry.entry_id)
   schedules = entry.options.get("schedules", [])
   ```

2. **Never store options in instance variables across steps** - always fetch fresh

3. **Preserve all existing data when updating**:
   ```python
   new_schedules = dict(schedules)  # Copy existing
   new_schedules[schedule_id] = updated_schedule
   updated_options = {**entry.options, "schedules": new_schedules}
   ```

4. **Configuration field in edit flow**:
   ```python
   # In async_step_edit_schedule:
   if "configuration" in self._schedule_data and isinstance(self._schedule_data["configuration"], dict):
       self._schedule_data["configuration"] = yaml.dump(
           self._schedule_data["configuration"],
           default_flow_style=False,
           sort_keys=False
       ).strip()
   ```

5. **Configuration field schema**:
   ```python
   # Use default parameter to populate field
   vol.Optional("configuration", default=config_value): TemplateSelector()
   ```

6. **Configuration parsing**:
   ```python
   config_yaml = user_input.get("configuration") or ""
   config_yaml = config_yaml.strip() if isinstance(config_yaml, str) else ""
   if config_yaml:
       config_dict = yaml.safe_load(config_yaml)
       if isinstance(config_dict, dict):
           data["configuration"] = config_dict
   # If empty, don't include "configuration" key in data dict
   ```

### strings.json

Include `data_description` for configuration fields:
```json
{
  "options": {
    "step": {
      "configure_date": {
        "title": "Configure date schedule",
        "description": "Create a schedule based on specific dates...\n\nNote: To clear the configuration field, enter a single space character.",
        "data": {
          "configuration": "Configuration (YAML)"
        },
        "data_description": {
          "configuration": "Optional YAML configuration for this schedule. To clear, enter a single space."
        }
      }
    }
  }
}
```

## Testing Requirements

### Test Coverage Areas
1. **Config flow tests**: All flow paths (add, edit, remove, default config)
2. **Schedule generator tests**: All schedule types, edge cases, overlap detection
3. **Calendar tests**: Event generation, year wrapping, configuration handling
4. **Integration tests**: Full setup/unload cycle
5. **Persistence tests**: Verify schedules are properly saved and loaded
6. **Diagnostics tests**: All schedule types, configuration handling, data structure

### Critical Test Scenarios
- Adding multiple schedules without overwriting existing ones
- Editing schedules preserves other schedules
- Removing schedules preserves other schedules
- Year-wrapping schedules generate correct dates
- Overlap detection across multiple years
- Configuration inheritance (schedule-specific vs default)
- Invalid input validation (dates, YAML, overlaps)
- Name uniqueness validation (schedulers and schedules, case-insensitive)
- Editing schedules can keep same name
- Configuration dict to YAML string conversion when editing
- Configuration field displays existing YAML using `default` parameter
- Removing configuration by emptying the field
- Configuration field helper text is displayed in UI

### Diagnostics Test Scenarios
- Empty schedules (no schedules configured)
- Date-based schedules with all fields
- Week-based schedules with all fields
- Nth-day schedules with all fields
- Schedules with configuration data
- Schedules without configuration data
- Default configuration present
- Default configuration absent
- Multiple schedules of different types
- Configuration data structure integrity (dict format preserved)

## Quality and Standards

### Home Assistant Requirements
- Follow Home Assistant best practices (see AGENTS.md)
- Use proper type hints (Python 3.13+)
- Pass ruff linting and formatting
- Integration type: `helper`
- Quality scale: Silver or Gold
- All-day events only (no time components)
- Proper error handling with translated messages

### Code Quality
- Use constants from const.py for month/day/occurrence names
- Proper async/await patterns
- No blocking operations in event loop
- Clean separation of concerns (config flow, calendar, date generation)
- Comprehensive error handling
- Descriptive variable and function names

### Documentation
- Docstrings for all public functions
- Clear comments for complex logic
- README with setup and usage instructions
- SPEC.md (this document) for complete specification

## Success Criteria

The integration is complete when:
1. Users can create multiple schedulers with unique names
2. Each scheduler can have multiple schedules of all three types
3. Schedules can be added, edited, and removed without data loss
4. Configuration system works (default and per-schedule)
5. Calendar entity displays correct events for all schedule types
6. Year-wrapping schedules work correctly
7. Overlap detection prevents conflicting schedules
8. All validation rules are enforced with clear error messages
9. Configuration YAML is properly displayed when editing schedules
10. Diagnostics feature provides comprehensive troubleshooting data
11. All tests pass with >95% coverage (including diagnostics tests)
12. Code passes linting and formatting checks
13. Integration loads and unloads cleanly in Home Assistant
