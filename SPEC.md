# Home Assistant Scheduler Integration - Specification

**Domain**: `ha_scheduler`
**Version**: 0.4.2
**Quality Scale**: Gold
**Integration Type**: Service
**Status**: Implemented and functional

**Objective**: Create a Home Assistant custom integration called "HA Scheduler" that provides a service-based scheduling system with recurring annual calendar schedules, flexible date patterns, and optional YAML configuration.

## Key Requirements Summary

### 🎯 **Critical Requirements**
1. **Service-Based Architecture**: Transform from helper to service integration type
2. **Clean Calendar Entity IDs**: Format `calendar.{service_name}` without duplication
3. **Seamless Migration**: V1 to V2 upgrade with zero data loss and entity continuity
4. **Consistent Terminology**: Use "Default Configuration" not "Service Configuration"
5. **Single Calendar per Service**: Each service has exactly one calendar named after the service

### 🔧 **Technical Requirements**
- **Integration Type**: `service` (changed from `helper`)
- **Entity Naming**: `_attr_has_entity_name = False` to prevent ID duplication
- **Migration System**: Versioned functions supporting future upgrades
- **Data Structure**: Service-based options with nested schedules and configuration
- **Device Grouping**: All calendars grouped under scheduler service device

## Overview

This integration provides a service-based calendar scheduling system where:
- Users can create scheduler services (each is a separate config entry)
- Each service contains one or more calendars (currently one calendar per service)
- Each calendar can have multiple schedules that are all-day events recurring annually
- Four scheduling patterns are supported: by date, by week of month, by nth day of month, and by holiday
- Each schedule can have optional YAML configuration attached
- Migration system automatically upgrades from helper-based (v1) to service-based (v2) architecture

## Core Features

### Service-Based Architecture
- Users can add multiple independent scheduler services
- Each service is a separate config entry with its own calendar entity
- Services can be named during setup (must be unique, case-insensitive)
- Each service contains a single calendar with entity ID matching the service name
- Calendar entity ID format: `calendar.{service_name}` (no service prefix duplication)
- Future enhancement: Multiple calendars per service

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
Define a schedule using week occurrences within months with optional week type specification.

**User Input**:
- Start month (dropdown: January-December, stored as 1-12)
- Start week (dropdown: First/First full/Second/Third/Fourth/Last, stored as combined format)
- Start day of week (dropdown: Monday-Sunday/Whole week, stored as 0-6 where 0=Monday, optional)
- End month (dropdown: January-December, stored as 1-12)
- End week (dropdown: First/First full/Second/Third/Fourth/Last, stored as combined format)
- End day of week (dropdown: Monday-Sunday/Whole week, stored as 0-6, optional)

**Week Type Options**:
- **First** (partial): First week of month, may start in previous month (default)
- **First full**: First full week entirely within the month
- **Second/Third/Fourth/Last**: Always full weeks within the month

**Day of Week Options**:
- **Specific day**: Schedule applies to specific weekday (e.g., Monday to Friday)
- **Whole week**: Schedule applies to entire week (leave day fields empty)

**Behavior**:
- Dates vary each year based on calendar
- Only wraps to next year if end month < start month
- Week 4 (Last) means the last occurrence of that weekday in the month
- Country-specific week start conventions (Sunday vs Monday) are automatically detected
- Week type only applies to first week (occurrence 0), other weeks are always full
- Invalid weekday/week combinations that do not produce a valid recurring date range are rejected during configuration

**Examples**: 
- First Monday of March to Last Friday of June (specific days)
- First full week of March to Second week of June (whole weeks)
- First week of December to First week of January (year wrapping)

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

#### 4. By Holiday Schedule
Define a schedule anchored to a named holiday from the Python `holidays` provider.

**User Input**:
- Country (dropdown, stored as ISO 3166-1 alpha-2 code)
- Category (dropdown, stored as provider category code)
- Holiday name (dropdown, stored exactly as selected)
- Days before (number: 0-30) - start offset
- Days after (number: 0-30) - end offset

**Behavior**:
- Stores the selected `country_code`, `category`, and `holiday_name` as the rule definition
- Resolves the actual holiday date from the Python `holidays` library for each target year instead of pinning to a representative Gregorian date
- Applies `start_offset` / `end_offset` after the yearly holiday lookup
- Supports single-day and contiguous multi-day holiday names
- Uses the same offset semantics as nth-day schedules
- Does not reduce the holiday to a fixed `month/day` rule behind the scenes

**Example**: Good Friday in Germany, 1 day before to 2 days after

### Holiday Import System

#### Smart Holiday Detection
The integration includes a comprehensive holiday import feature that automatically creates schedules for holidays from any supported country.

**Supported Countries**: 499+ countries including US, Canada, UK, Germany, France, Australia, New Zealand, and many more.

**Dynamic Country Discovery**: Countries are discovered dynamically from the holidays library using `holidays.list_supported_countries()`, ensuring the latest coverage without hardcoded lists.

**Intelligent Country Naming**: 
- Uses Babel's territory data to get proper country names (e.g., "United States" instead of "US")
- Falls back to holidays library country names when Babel unavailable
- Graceful degradation to formatted country codes as last resort

**Holiday Categories**: Varies by country but typically includes:
- **Public**: National/federal holidays
- **Bank**: Banking holidays  
- **School**: School holidays and breaks
- **Observance**: Cultural and religious observances
- **Optional**: Optional or regional holidays

#### Pattern Analysis
The system automatically analyzes holidays across multiple years (dynamic range: `today.year ± CALENDAR_YEAR_LOOKAROUND`) to determine the optimal schedule type:

**Fixed Date Holidays** (e.g., Independence Day, Christmas):
- Same date every year (July 4th, December 25th)
- Creates "Date" type schedules
- Pattern description: "Fixed date: July 04"

**Variable Date Holidays** (e.g., Martin Luther King Jr. Day, Thanksgiving):
- Date varies based on weekday occurrence in month
- Creates "Nth-Day" type schedules  
- Pattern description: "Third Monday of January", "Fourth Thursday of November"
- **Occurrence Calculation**: Uses `calculate_occurrence()` to determine if holiday is 1st, 2nd, 3rd, 4th, or last occurrence of weekday

**Holiday-Backed Movable Holidays** (e.g., Good Friday, Easter Monday):
- Holidays that cannot be safely represented as Date, Week, or Nth-Day rules
- Creates "Holiday" type schedules that store the holiday identity and resolve dates from the Python `holidays` library year by year
- Pattern description: "Holiday-backed (resolved each year)"

**Multi-Day Week Holidays** (e.g., Spring Break, Holiday Weeks):
- Holidays spanning multiple consecutive days in the same week or across weeks
- Creates "Week" type schedules with appropriate week types
- Uses "partial" week type (default) for first weeks to match typical holiday patterns
- Pattern description: "First week of March (Monday to Friday)", "First Monday to Second Friday of March"
- **Advanced Week Pattern Detection**:
  1. Groups dates by year for consistency analysis
  2. Checks for consecutive days within same month (1-6 day spans)
  3. Validates pattern consistency across multiple years
  4. Calculates start/end week occurrences using `calculate_occurrence()`
  5. Determines appropriate week types (partial/full) based on holiday characteristics

**Single Occurrence Holidays**:
- Holidays with only one date in dataset
- Creates "Date" type schedule using available date
- Pattern description: "Single occurrence: March 15"

#### Advanced Pattern Analysis Algorithms

**`analyze_holiday_pattern(dates: list[date]) -> dict[str, Any] | None`**
- Main pattern analysis function that processes holiday dates across multiple years
- **Fixed Date Detection**: Checks if all dates have same month/day across years
- **Variable Date Analysis**: For non-fixed dates, analyzes weekday patterns and occurrences
- **Week Pattern Fallback**: Calls `_analyze_week_pattern()` for complex multi-day holidays
- **Holiday Fallbacks**: Import flow converts unrecognizable movable-date patterns into holiday-backed schedules

**`_analyze_week_pattern(dates: list[date]) -> dict[str, Any] | None`**
- Specialized function for detecting week-based holiday patterns
- **Year Grouping**: Groups dates by year for cross-year consistency analysis
- **Consecutive Day Detection**: Identifies holidays spanning 2-6 consecutive days
- **Same Month Validation**: Ensures all dates in pattern are within same month
- **Cross-Year Consistency**: Validates pattern holds across multiple years
- **Week Type Assignment**: Defaults to "partial" type for holiday compatibility
- **Pattern Description Generation**: Creates human-readable pattern descriptions

**`calculate_occurrence(target_date: date) -> int | None`**
- Calculates which occurrence of weekday in month (0-4, where 4=last)
- **First Occurrence Calculation**: Finds first occurrence of target weekday in month
- **Occurrence Counting**: Counts weeks from first occurrence to target date
- **Last Occurrence Detection**: Checks if next occurrence would be in following month
- **Robust Error Handling**: Returns None for invalid dates or calculation errors

**`format_date_localized(date_obj: date, locale_code: str | None = None) -> str`**
- Formats dates using Babel's locale-aware formatting when available
- **Babel Integration**: Uses `babel.dates.format_date()` for proper localization
- **Fallback Formatting**: Uses Python's `strftime()` when Babel unavailable
- **Locale Handling**: Supports custom locale codes or defaults to English

#### Conflict Resolution
- **Name Conflicts**: Option to overwrite existing schedules with same name
- **Date Overlaps**: Option to skip holidays that would overlap with existing schedules, including overwrite replacements that would collide with other schedules
- **Holiday overlap horizon**: Any overlap check involving a holiday-backed schedule validates an extended provider-backed future window (`current_year..current_year+10`)
- **Holiday overlap horizon**: Any overlap check involving a holiday-backed schedule validates an extended provider-backed future window (`current_year..current_year+10`)
- **Country Name Flag**: Option to include/exclude country code in schedule names
- **Detailed Feedback**: Shows exactly what was imported, skipped, or overwritten

#### Implementation Details
- Uses `holidays` Python library (version 0.34+) for comprehensive holiday data
- **Async Processing**: All holiday data operations use `run_in_executor` to prevent blocking event loop
- **Lazy Imports**: Babel and holidays libraries imported inside functions to avoid blocking I/O during module import
- **Graceful Fallback**: Complete feature gracefully disabled when holidays library unavailable
- **Comprehensive Error Handling**: Individual holiday processing errors don't stop entire import
- **Multi-Year Analysis**: Pattern analysis across a dynamic year range (`today.year ± CALENDAR_YEAR_LOOKAROUND`) for accuracy; never hardcodes specific years
- **Category Support**: Dynamic category discovery per country with fallback to "public" holidays
- **Localization Support**: Babel integration for proper country names and date formatting

#### Async Operation Patterns
All holiday import functions follow async patterns:

**`get_supported_countries() -> dict[str, str]`**
- Async wrapper around `_get_supported_countries_sync()`
- Uses `loop.run_in_executor(None, _get_supported_countries_sync)`
- Returns sorted dict of country_code: country_name pairs

**`get_available_categories(country_code: str) -> dict[str, str]`**
- Async wrapper around `_get_available_categories_sync(country_code)`
- Tests category support by attempting to create holidays with each category
- Returns dict of category_code: category_name pairs

**`get_holidays_for_country(country_code: str, categories: list[str]) -> dict[str, dict[str, Any]]`**
- Async wrapper around `_get_holidays_for_country_sync(country_code, categories)`
- Processes holidays across multiple years and categories
- Returns comprehensive holiday data with analyzed patterns

### Configuration System

#### Default Configuration
- Each service can have a default YAML configuration
- Accessed via "Default configuration" option in the options menu (not "Service configuration")
- Stored in `config_entry.options["services"]["default"]["configuration"]`
- Exposed as calendar entity attribute `default_configuration`
- Used when a schedule doesn't have its own configuration
- Terminology: Always use "Default Configuration" in UI, never "Service Configuration"

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
2. Prompt for "Scheduler Name" (default: "Scheduler")
3. Validate name is unique across all scheduler services (case-insensitive)
4. Create config entry with service-based structure containing default service

### Options Flow - Main Menu
Present menu with five options:
- Add schedule
- Edit schedule
- Remove schedule
- Import holidays
- Default configuration

### Add Schedule Flow
1. **Step 1**: Select schedule type
   - Radio/dropdown: By Date, By Week of Month, By Nth Day of Month, By Holiday
   
2. **Step 2**: Single-page form with all parameters for Date, Week, and Nth-Day schedules
   - Schedule name (text input, required)
   - All schedule-specific parameters (dates/weeks/occurrences)
   - **Week Type Integration**: For week schedules, week selectors show:
     - "First" (partial week, may start in previous month) - stored as "0_partial"
     - "First full" (full week entirely within month) - stored as "0_full"
     - "Second", "Third", "Fourth", "Last" (always full weeks) - stored as "1", "2", "3", "4"
   - **Optional Day Fields**: Day of week fields can be left as "Whole week" for entire week scheduling
   - Configuration (YAML, optional, TemplateSelector)
   - Validate all inputs on this page
   - Show errors inline if validation fails
   
3. **On Submit**:
   - Generate unique UID using `str(uuid.uuid4())`
   - Validate schedule name is unique within this service (case-insensitive)
   - Check for overlaps with existing schedules across the full 400-year Gregorian recurrence cycle
   - Add to `config_entry.options["services"]["default"]["schedules"]` dict
   - Preserve all existing schedules

4. **Holiday schedule path**:
   - **Step 2a**: Select holiday country
   - **Step 2b**: Select holiday category
   - **Step 2c**: Select named holiday, offsets, and optional YAML configuration
   - Validate that the selected holiday still exists when the final form is submitted

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
   - Update schedule in `config_entry.options["services"]["default"]["schedules"]` dict
   - Preserve all other schedules

### Remove Schedule Flow
1. **Step 1**: Select schedule from dropdown (shows schedule names)
   
2. **Step 2**: Confirmation dialog
   - Show schedule name and type
   - Checkbox: "Confirm removal"
   - Only proceed if checkbox is checked
   
3. **On Confirm**:
   - Remove schedule from `config_entry.options["services"]["default"]["schedules"]` dict
   - Preserve all other schedules

### Import Holidays Flow
1. **Step 1**: Select country from 499+ available options
   - Dynamic dropdown populated from holidays library
   - Countries sorted alphabetically by name
   - Includes major countries like US, CA, GB, DE, FR, AU, NZ, etc.

2. **Step 2**: Select holiday categories (optional)
   - Multiple selection from available categories for the chosen country
   - Common categories: Public, Bank, School, Observance, Optional
   - Categories vary by country and are dynamically determined
   - Default to "Public" if no categories available

3. **Step 3**: Select specific holidays and import options
   - Multiple selection from available holidays with pattern descriptions (all holidays selected by default)
   - Each holiday shows detected pattern (e.g., "Fixed date: July 04" or "Third Monday of January")
   - Import options:
     - **Overwrite existing**: Replace schedules with same name (default: false)
     - **Skip on overlap**: Skip holidays that would overlap with existing schedules, including overwrite replacements that would collide with other schedules (default: true)
     - **Include country name**: Add country code to schedule names (default: false)
     - **Use holiday type**: Import selected holidays as `holiday` schedules instead of the detected Date, Week, or Nth-Day pattern (default: true)
   - Validation: At least one holiday must be selected

4. **On Import**:
   - Create `holiday` schedules by default, unless the user disables that option and forces pattern-based import
   - Handle name conflicts based on overwrite setting
   - Handle date overlaps based on skip setting
   - Generate schedule names: "{Holiday Name} ({Country})" or "{Holiday Name}" based on flag
   - Show import results: imported count, skipped count, overwritten count, errors
   - **Error message truncation**: When all selected holidays fail to import, show the first 3 error reasons followed by `" (and N more)"` if there are additional errors beyond 3:
     ```python
     shown = errors[:3]
     suffix = f" (and {len(errors) - 3} more)" if len(errors) > 3 else ""
     error_message = "No holidays were imported. " + "; ".join(shown) + suffix
     ```

### Default Configuration Flow
1. Single-page form with YAML input (TemplateSelector)
2. Pre-fill with current default configuration if exists
3. Validate YAML syntax and structure
4. Save to `config_entry.options["services"]["default"]["configuration"]`

## Validation Rules

### Schedule Parameters
- Days: Must be 1-31 (will be clamped to valid days for the month)
- Offsets: Must be 0-30
- For by_date: End date must be after start date (considering year wrapping)
- For by_week and by_nth_day: End can be before start in same year
- For by_week: The selected weeks and weekdays must produce a valid, non-reversed recurring date range

### Name Uniqueness
- **Service names**: Must be unique across all scheduler services (case-insensitive)
  - Error: "Name already exists. Please choose a different name."
  
- **Schedule names**: Must be unique within each service (case-insensitive)
  - Error: "A schedule with this name already exists. Please choose a different name."
  - When editing: Allow keeping the same name (exclude current schedule from check)

### Overlap Detection
- Check if new/edited schedule overlaps with existing schedules
- Check across one full Gregorian calendar cycle (400 years) for Date, Week, and Nth-Day schedules to avoid time-dependent false negatives
- Any comparison involving a Holiday schedule checks an extended provider-backed horizon (`current_year..current_year+10`)
- Return tuple: `(has_overlap: bool, conflicting_schedule_name: str | None)`
- Error: "This schedule overlaps with '{conflicting_schedule}'"
- When editing: Exclude current schedule from overlap check

### YAML Configuration Validation
- Must be valid YAML syntax
- Must parse to a dict or list (not a simple string/number)
- Empty string or whitespace-only is valid (removes configuration)
- Error messages should be descriptive (e.g., "Invalid YAML: {error}")

### Holiday Import Validation
- **Country Selection**: Must select a valid country from supported list
- **Holiday Selection**: At least one holiday must be selected for import
- **Name Conflicts**: Handled based on "overwrite existing" flag setting
- **Date Overlaps**: Handled based on "skip on overlap" flag setting
- **Pattern Analysis**: Movable holidays that do not fit Date, Week, or Nth-Day rules import as Holiday schedules
- **Error Handling**: Graceful handling when holidays library unavailable
- **Async Operations**: All holiday data fetching uses `run_in_executor` for non-blocking operations

## Data Storage

### Config Entry Structure
```python
{
    "data": {
        "scheduler_name": "My Scheduler"  # Service name
    },
    "options": {
        "services": {
            "default": {  # Service ID (currently always "default")
                "name": "My Scheduler",  # Service display name
                "schedules": {
                    "uuid-string": {
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
                        "start_week_type": "partial", # "partial" or "full" (only for start_week=0)
                        "start_day_of_week": 0,     # 0-6 (0=Monday) - optional
                        "end_month": 6,             # 1-12
                        "end_week": 4,              # 0-4
                        "end_week_type": "partial", # "partial" or "full" (only for end_week=0)
                        "end_day_of_week": 4,       # 0-6 - optional
                        "country_code": "US",       # ISO country code for week start detection - optional
                        
                        # For schedule_type="nth-day":
                        "month": 3,            # 1-12
                        "occurrence": 1,       # 0-4 (0=first, 4=last)
                        "day_of_week": 1,      # 0-6 (0=Monday)
                        "start_offset": 2,     # days before (0-30)
                        "end_offset": 3,       # days after (0-30)
                        
                        # Optional for all types:
                        "configuration": {"key": "value"}  # dict or omitted
                    }
                },
                "configuration": {"default": "config"}  # dict or omitted
            }
        }
    }
}
```

### Field Naming Conventions
- Schedule type field: `schedule_type` (values: "date", "week", "nth-day")
- Offset fields: `start_offset`, `end_offset` (not "days_before"/"days_after")
- Week occurrence: `start_week`, `end_week` (0-4)
- Week type: `start_week_type`, `end_week_type` ("partial" or "full", only for occurrence 0)
- Occurrence: `occurrence` (0-4 where 0=first, 4=last)
- Day of week: `day_of_week`, `start_day_of_week`, `end_day_of_week` (0-6 where 0=Monday, optional for week schedules)
- Country code: `country_code` (ISO 3166-1 alpha-2 format, optional, for week start detection)
- Months: 1-12 (1=January, 12=December)

## Calendar Entity Implementation

### Entity Naming and IDs
- **Entity ID Format**: `calendar.{service_name}` (clean, no duplication)
- **has_entity_name**: Set to `False` to avoid service name duplication in entity ID
- **Unique ID**: 
  - For default service (migrated from v1): `{entry_id}` (maintains backward compatibility)
  - For additional services: `{entry_id}_{service_id}` for internal tracking
- **Display Name**: Uses the service name directly
- **Critical Requirement**: Entity ID should only be the calendar name, not include service name twice
- **Migration Compatibility**: Default service maintains original unique ID to prevent entity duplication during v1→v2 migration

### Entity ID Examples
- ✅ **Correct**: `calendar.my_scheduler` (service name: "My Scheduler")
- ❌ **Incorrect**: `calendar.my_scheduler_my_scheduler` (duplicated name)
- ✅ **Correct**: `calendar.home_schedule` (service name: "Home Schedule")
- ❌ **Incorrect**: `calendar.home_schedule_home_schedule` (duplicated name)

### Event Generation
- Generate events for requested date range
- Include previous year to catch year-wrapping schedules
- Each event has unique UID: `{schedule_uid}_{year}`
- All events are all-day events
- End date is exclusive (add 1 day for calendar display)
- **Active/upcoming event selection** (`event` property): scans `±CALENDAR_YEAR_LOOKAROUND` years from today using the `CALENDAR_YEAR_LOOKAROUND` constant (7-year window total), returns the active event when one is in progress, and otherwise returns the next upcoming event

### Event Properties
- **summary**: Schedule name
- **start**: Start date (date object, not datetime)
- **end**: End date + 1 day (for all-day event display)
- **description**: Configuration dict (not string) - schedule-specific or default
- **uid**: `{schedule_uid}_{year}`

### Entity Attributes
- `default_configuration`: The service's default YAML configuration dict
- `configuration`: When an event is active or upcoming, contains the configuration dict for that schedule
- `name`: Active schedule name, or the next upcoming schedule name when the calendar is idle
- `schedule_uid`: Active schedule UID, or the next upcoming schedule UID when the calendar is idle

### Device Integration
- All calendars are grouped under a device representing the scheduler service
- Device info includes service name, manufacturer, and model information
- Enables better organization in Home Assistant UI

### Update Handling
- Listen for config entry options changes
- Regenerate events when schedules are added/edited/removed
- Update calendar entity state
- Support for service-based data structure

## Migration System

### Version Management
- **Current Version**: 2 (service-based architecture)
- **Previous Version**: 1 (helper-based architecture)
- **Config Flow Version**: 2.1
- **Manifest Version**: 0.4.2

### Migration Process
The integration automatically detects and migrates older config entries:

1. **Detection**: Check `entry.version < CURRENT_VERSION` in `async_setup_entry`
2. **Migration**: Call `async_migrate_entry(hass, entry)` 
3. **Transformation**: Convert helper structure to service structure
4. **Preservation**: All existing schedules and configurations are preserved
5. **Calendar Continuity**: Calendar entity IDs remain the same after migration
6. **Update**: Config entry version is updated to current version

### Migration Requirements
- **Seamless Upgrade**: Users should not notice any functional changes
- **Data Integrity**: Zero data loss during migration
- **Entity Continuity**: Calendar entity IDs must remain consistent (no duplicate entities created)
- **Unique ID Preservation**: Default service maintains original unique ID format to prevent entity duplication
- **Backward Compatibility**: Support for future migrations with versioned functions

### Migration Functions

**`migrations.py`** contains versioned migration functions:
- `async_migrate_v1_to_v2()` - Helper to service transformation
- Future migrations follow pattern `async_migrate_vX_to_vY()`

#### Migration System Architecture

**Version Detection and Routing**:
```python
async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to current version."""
    if entry.version == 1:
        return await async_migrate_v1_to_v2(hass, entry)
    # Future migrations would be added here
    return True
```

**Atomic Migration Process**:
1. **Backup Original Data**: Preserve original structure before transformation
2. **Transform Data Structure**: Convert helper model to service model
3. **Validate Migration**: Ensure all data preserved and structure correct
4. **Update Version**: Set entry.version to current version
5. **Entity Continuity**: Maintain original unique IDs to prevent duplicate entities

**Migration Safety Features**:
- **Non-destructive**: Original data preserved during transformation
- **Rollback Capability**: Migration failures don't corrupt existing data
- **Validation Checks**: Verify data integrity after migration
- **Logging**: Comprehensive logging for troubleshooting migration issues

### V1 to V2 Migration Details

**Before (Helper Model)**:
```python
{
    "data": {},
    "options": {
        "schedules": {"schedule_id": {...}},
        "configuration": {...}
    }
}
```

**After (Service Model)**:
```python
{
    "data": {"scheduler_name": "Service Name"},
    "options": {
        "services": {
            "default": {  # Default service preserves original entity unique ID
                "name": "Service Name",
                "schedules": {"schedule_id": {...}},  # All existing schedules preserved
                "configuration": {...}  # Existing configuration preserved
            }
        }
    }
}
```

**Entity Unique ID Handling**:
- **Before Migration**: Calendar entity unique ID = `{entry_id}`
- **After Migration**: Default service calendar unique ID = `{entry_id}` (unchanged)
- **Result**: No duplicate entities created, existing calendar entity continues to work
- **Future Services**: Additional services use `{entry_id}_{service_id}` format

## Implementation Details

### File Structure
```
custom_components/ha_scheduler/
├── __init__.py                 # Setup/unload entry points with migration support
├── manifest.json              # Integration metadata (service type, holidays dependency)
├── const.py                   # Constants (DOMAIN, month/day/occurrence names)
├── config_flow.py             # Config and options flows (service-based, holiday import)
├── calendar.py                # Calendar entity implementation (service-aware)
├── schedule_generator.py      # Date calculation logic
├── holiday_importer.py        # Holiday import functionality (async)
├── diagnostics.py             # Diagnostics data collection (service-based)
├── migrations.py              # Migration system (v1 to v2)
├── strings.json              # UI text and translations
├── quality_scale.yaml         # Home Assistant quality scale compliance
└── translations/
    └── en.json               # English translations
```

### manifest.json
Integration metadata and dependencies:
```json
{
  "domain": "ha_scheduler",
  "name": "HA Scheduler",
  "codeowners": ["@Smiley73"],
  "config_flow": true,
  "documentation": "https://github.com/Smiley73/ha-scheduler",
  "integration_type": "service",
  "iot_class": "calculated",
  "issue_tracker": "https://github.com/Smiley73/ha-scheduler/issues",
  "quality_scale": "gold",
  "requirements": ["holidays>=0.34", "babel>=2.0.0"],
  "version": "0.4.1"
}
```

**Key Requirements**:
- **Integration Type**: `service` (not helper)
- **Quality Scale**: `gold` level compliance
- **Dependencies**: `holidays>=0.34` for holiday import functionality, `babel>=2.0.0` for localization
- **Config Flow**: UI-based configuration required
- **Version**: 0.4.1 includes holiday import feature with improved code quality

### const.py
Define constants:
```python
DOMAIN = "ha_scheduler"

# Calendar event window: generate events ±CALENDAR_YEAR_LOOKAROUND years from today
CALENDAR_YEAR_LOOKAROUND = 3  # used in calendar.py and holiday_importer.py

# Internal keys (lowercase, used for option values and data storage)
MONTH_NAMES = ["january", "february", "march", ...]  # 12 items
DAY_NAMES = ["monday", "tuesday", "wednesday", ...]  # 7 items
OCCURRENCE_NAMES = ["first", "second", "third", "fourth", "last"]  # 5 items

# Display labels (Title Case, used in UI dropdowns and holiday pattern descriptions)
MONTH_NAMES_DISPLAY = ["January", "February", "March", ...]  # 12 items
DAY_NAMES_DISPLAY = ["Monday", "Tuesday", "Wednesday", ...]  # 7 items
OCCURRENCE_NAMES_DISPLAY = ["First", "Second", "Third", "Fourth", "Last"]  # 5 items
```

**Key rule**: `MONTH_NAMES_DISPLAY`, `DAY_NAMES_DISPLAY`, and `OCCURRENCE_NAMES_DISPLAY` are the single source of truth for human-readable name arrays. They must not be duplicated inline in `config_flow.py`, `holiday_importer.py`, or `diagnostics.py` — import from `const.py` instead.

### diagnostics.py
Implement comprehensive diagnostics data collection:

**`async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]`**
- Collect diagnostic information for troubleshooting
- Include entry metadata (title, entry_id)
- Include schedule count and detailed schedule information
- Include schedule-specific fields based on type (date, week, nth-day)
- Include configuration data (both schedule-specific and default)
- Never expose sensitive data (no passwords, tokens, or coordinates)

#### Diagnostic Data Collection Strategy

**Service-Based Structure Analysis**:
- Iterates through all services in config entry options
- Collects schedule counts and detailed schedule information per service
- Includes service-level configuration data when present
- Provides summary statistics (total services, total schedules)

**Schedule Type-Specific Data**:
- **Date Schedules**: Includes start_month, start_day, end_month, end_day
- **Week Schedules**: Includes start_month, start_week, start_week_type, start_day_of_week, end_month, end_week, end_week_type, end_day_of_week, country_code
- **Nth-Day Schedules**: Includes month, occurrence, day_of_week, start_offset, end_offset

**Configuration Data Handling**:
- Includes boolean flags for configuration presence (has_configuration)
- Includes actual configuration content for troubleshooting
- Separates schedule-specific vs default configuration
- Maintains data structure integrity (preserves dict/list types)

**Privacy and Security**:
- Schedule names and service names included for context
- Entry IDs included for correlation but are not sensitive
- Configuration content is passed through `async_redact_data` with a set of common sensitive key names (e.g., `api_key`, `password`, `token`, `secret`) before inclusion, so user-stored credentials are automatically masked

**Diagnostic Data Structure**:
```python
{
    "entry": {
        "title": "Scheduler Name",
        "entry_id": "config_entry_id",
        "scheduler_name": "Service Name"
    },
    "services": {
        "default": {
            "name": "Service Name",
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
                "has_configuration": True,
                "configuration": {"default": "config"}  # if present
            }
        }
    },
    "summary": {
        "total_services": 1,
        "total_schedules": 2
    }
}
```

### calendar.py

**Calendar Entity Requirements**:
1. **Entity Naming**: 
   ```python
   class SchedulerCalendar(CalendarEntity):
       _attr_has_entity_name = False  # Critical: Prevents name duplication
   ```

2. **Entity ID Generation**:
   ```python
   # Entity ID should be: calendar.{service_name}
   # NOT: calendar.{service_name}_{service_name}
   
   # Maintain backward compatibility for unique ID
   if service_id == "default":
       self._attr_unique_id = entry.entry_id  # Original format for migration compatibility
   else:
       self._attr_unique_id = f"{entry.entry_id}_{service_id}"  # New services
   
   self._attr_name = service_name  # Direct service name, no prefix
   ```

3. **Service-Based Data Access**:
   ```python
   def _get_schedules(self) -> list[dict[str, Any]]:
       services = self._entry.options.get("services", {})
       service_data = services.get(self._service_id, {})
       schedules_dict = service_data.get("schedules", {})
       return list(schedules_dict.values())
   ```

4. **Device Integration**:
   ```python
   from homeassistant.helpers.device_registry import DeviceInfo
   self._attr_device_info = DeviceInfo(
       identifiers={("ha_scheduler", entry.entry_id)},
       name=entry.title,
       manufacturer="HA Scheduler",
       model="Scheduler Service",
   )
   ```

5. **Parallel Updates**: Set `PARALLEL_UPDATES = 0` at module level (no external I/O).

6. **Update Listener**: Register the config entry update listener in `async_added_to_hass()`, not in `__init__`, so it only activates after the entity is fully registered with the entity registry.

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
- Handle week-based schedules with week type support
- Support optional day of week fields (whole week scheduling)
- Use separate `start_week_type` and `end_week_type` for first weeks
- Support country-specific week start conventions
- Find nth occurrence of weekday in month
- Only wrap to next year if end_month < start_month
- **Effective Week Type Logic**: When start and end are in same month, use `start_week_type` for consistency
- **Four Calculation Modes**:
  1. **Whole week to whole week**: Both day fields empty - uses `_get_week_start` and `_get_week_end`
  2. **Specific day to whole week end**: Only start day specified - uses `_get_weekday_in_week` for start
  3. **Whole week start to specific day**: Only end day specified - uses `_get_week_end` for end
  4. **Specific day to specific day**: Both days specified - uses `_get_weekday_in_week` for both

**`_get_week_start(year: int, month: int, occurrence: int, first_weekday: int, week_type: str) -> date`**
- Find the start of the nth week in a month
- Support "partial" (may start in previous month) and "full" (entirely within month) types
- Handle country-specific first weekday (0=Monday, 6=Sunday)
- **Partial Week Adjustment**: For partial first weeks that would start in previous month, returns first day of target month instead
- **Subsequent Week Alignment**: For partial type with adjusted first week, subsequent weeks (occurrence > 0) realign to proper calendar week boundaries
- **Calendar Week Calculation**: Uses `(first_day.weekday() - first_weekday) % 7` to find calendar week boundaries
- **Last Week Handling**: For occurrence 4 (last), works backwards from last day of month to find week start

**`_get_week_end(year: int, month: int, occurrence: int, first_weekday: int, week_type: str) -> date`**
- Find the end of the nth week in a month
- Support week type for proper week boundary calculation
- Handle month boundaries correctly
- **Partial Week End Calculation**: For adjusted partial first weeks, finds actual calendar week end or month end (whichever is earlier)
- **Calendar Week Boundaries**: Calculates theoretical 7-day week span from calendar week start
- **Month Boundary Respect**: Never extends beyond month boundary except for last week (occurrence 4)

**`_get_weekday_in_week(year: int, month: int, week_occurrence: int, day_of_week: int, first_weekday: int, week_type: str) -> date`**
- Get specific weekday within a specific week of a month
- Uses `_get_week_start` and `_get_week_end` to define week boundaries
- Iterates through week days to find matching weekday
- Returns None if requested weekday doesn't exist in the specified week
- **Week Type Inheritance**: Uses same week_type parameter as the week boundary functions

**`get_country_first_weekday(country_code: str | None) -> int`**
- Determine first weekday for a country (0=Monday, 6=Sunday)
- Support 50+ countries with Sunday-first vs Monday-first conventions
- Default to Monday-first (0) for unknown countries
- **Babel Integration**: Uses Babel library's locale data for comprehensive country coverage
- **Fallback System**: Static mapping for countries not well-covered by Babel (JP, KR, MX, IL, SA, etc.)
- **Graceful Degradation**: Falls back to Monday-first if Babel unavailable or locale unknown

### Advanced Week Calculation Algorithms

#### Partial Week Type Algorithm
The "partial" week type implements sophisticated logic to handle first weeks that may start in the previous month:

**First Week Adjustment**:
1. Calculate theoretical calendar week start: `first_day - timedelta(days=(first_day.weekday() - first_weekday) % 7)`
2. If calendar week start is in previous month, adjust to first day of target month
3. This creates a "partial" week that starts mid-calendar-week

**Subsequent Week Realignment**:
For occurrence > 0 with adjusted partial first week:
1. Calculate `days_to_next_week_start = (first_weekday - first_day.weekday()) % 7`
2. If first day is already the week start day, add 7 days to go to next week
3. Find `next_calendar_week_start = first_day + timedelta(days=days_to_next_week_start)`
4. Calculate target week: `next_calendar_week_start + timedelta(weeks=occurrence - 1)`

This ensures subsequent weeks follow proper calendar boundaries even when first week was adjusted.

#### Full Week Type Algorithm
The "full" week type ensures the first week is entirely within the target month:

**First Week Selection**:
1. Calculate theoretical calendar week start
2. If calendar week start is in previous month, skip to next calendar week
3. This guarantees the entire first week falls within the target month

**Consistent Week Progression**:
All subsequent weeks are calculated from the first full week start, maintaining 7-day intervals.

#### Effective Week Type Logic
When start and end weeks are in the same month, the system uses `start_week_type` for both boundaries to ensure consistency. This prevents mismatched week type interpretations within the same month context.

#### Country-Specific Week Start Handling
The system automatically detects and handles different week start conventions:
- **Monday-first countries** (most of Europe, Asia): `first_weekday = 0`
- **Sunday-first countries** (US, Canada, Japan, etc.): `first_weekday = 6`
- **Automatic detection** via Babel locale data or fallback mapping

**`_generate_by_nth_day(schedule: dict, year: int) -> list[tuple[date, date]]`**
- Handle nth-day schedules
- Find nth occurrence of weekday in month
- Apply start_offset (days before) and end_offset (days after)

**`_get_nth_weekday(year: int, month: int, occurrence: int, day_of_week: int) -> date`**
- Find the nth occurrence (0-3) or last (4) of a weekday in a month
- Return the date of that occurrence

**`check_overlap(new_schedule: dict, existing_schedules: list[dict], exclude_uid: str | None = None) -> tuple[bool, str | None]`**
- Check if new_schedule overlaps with any existing schedules
- Check across one full 400-year Gregorian cycle so recurring patterns are validated deterministically
- Exclude schedule with exclude_uid from check (for editing)
- Return (has_overlap, conflicting_schedule_name)

### config_flow.py

**Critical Implementation Requirements**:

0. **Shared conflict validation helper** — `_validate_schedule_conflicts()` in `OptionsFlowHandler` consolidates the duplicate-name + overlap checks that previously appeared in three separate step methods (add, edit, holiday import). Call this helper from each step instead of duplicating the logic:
   ```python
   def _validate_schedule_conflicts(
       self, schedule_data: dict, exclude_uid: str | None = None
   ) -> dict[str, str]:
       """Check for duplicate name and overlap; return errors dict."""
   ```

1. **Always use fresh options data**:
   ```python
   entry = self.hass.config_entries.async_get_entry(self.config_entry.entry_id)
   services = entry.options.get("services", {})
   schedules = services.get("default", {}).get("schedules", {})
   ```

2. **Never store options in instance variables across steps** - always fetch fresh

3. **Preserve all existing data when updating**:
   ```python
   new_schedules = dict(schedules)  # Copy existing
   new_schedules[schedule_id] = updated_schedule
   # Update service structure
   new_services = dict(services)
   new_services["default"] = {
       **new_services.get("default", {}),
       "schedules": new_schedules
   }
   updated_options = {**entry.options, "services": new_services}
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

6. **Configuration parsing and validation**:
   ```python
   config_yaml = user_input.get("configuration") or ""
   config_yaml = config_yaml.strip() if isinstance(config_yaml, str) else ""
   if config_yaml:
       try:
           config_dict = yaml.safe_load(config_yaml)
           # Validate it's a structure (dict/list), not a simple value
           if isinstance(config_dict, (dict, list)):
               data["configuration"] = config_dict
           else:
               errors["configuration"] = "Configuration must be a YAML structure (dict or list), not a simple value"
       except yaml.YAMLError as e:
           errors["configuration"] = f"Invalid YAML: {e}"
   # If empty, don't include "configuration" key in data dict
   ```

#### Configuration Field Requirements and Validation

**YAML Structure Validation**:
- Must be valid YAML syntax using `yaml.safe_load()`
- Must parse to a dict or list structure, not simple string/number values
- Empty or whitespace-only input removes the configuration (valid operation)
- Descriptive error messages for syntax errors and structure validation

**Field Display Logic**:
- Edit forms use `default` parameter (not `suggested_value`) to show existing YAML
- Configuration dict converted to YAML string using `yaml.dump(default_flow_style=False, sort_keys=False)`
- Helper text included: "To clear the configuration field, enter a single space character"

**Data Storage Patterns**:
- Configuration stored as dict in schedule data structure
- Exposed in CalendarEvent.description as dict (not string)
- Default configuration stored in service-level options
- Schedule-specific configuration overrides default when present

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

### Test Infrastructure

**`tests/conftest.py`** provides shared fixtures and helpers for all tests:
- `create_service_entry` fixture — factory function returning `MockConfigEntry` with the `services` structure; accepts `title`, `schedules`, and `configuration` kwargs
- `get_schedules_from_entry(entry)` — module-level helper to extract schedules dict from a service entry
- `get_configuration_from_entry(entry)` — module-level helper to extract configuration dict from a service entry
- All new tests should use these fixtures instead of defining local helpers
- All `MockConfigEntry` instances must use the `services` structure (not legacy `schedules`/`configuration` at top level)

### Test Coverage Areas
1. **Config flow tests**: All flow paths (add, edit, remove, import holidays, default config)
2. **Schedule generator tests**: All schedule types, edge cases, overlap detection
3. **Calendar tests**: Event generation, year wrapping, configuration handling, entity ID validation, `CALENDAR_YEAR_LOOKAROUND` constant value, 7-year event window
4. **Integration tests**: Full setup/unload/reload cycle
5. **Persistence tests**: Verify schedules are properly saved and loaded
6. **Diagnostics tests**: All schedule types, configuration handling, service-based data structure
7. **Migration tests**: V1 to V2 migration, data preservation, entity continuity
8. **Holiday import tests**: Country discovery, category detection, pattern analysis, conflict resolution
9. **Multi-service tests**: Multiple services per config entry, independent calendars and schedules, per-service unique IDs and default configurations

### Critical Test Scenarios
- Adding multiple schedules without overwriting existing ones
- Editing schedules preserves other schedules
- Removing schedules preserves other schedules
- Year-wrapping schedules generate correct dates
- Overlap detection across multiple years
- Configuration inheritance (schedule-specific vs default)
- Invalid input validation (dates, YAML, overlaps)
- Name uniqueness validation (services and schedules, case-insensitive)
- Editing schedules can keep same name
- Configuration dict to YAML string conversion when editing
- Configuration field displays existing YAML using `default` parameter
- Removing configuration by emptying the field
- Configuration field helper text is displayed in UI
- **Calendar entity ID validation**: Ensure clean entity IDs without duplication
- **Service-based data structure**: All tests use proper service-based config entries
- **Migration testing**: V1 to V2 migration preserves all data and entity IDs
- **Entity ID continuity**: Verify no duplicate entities are created during migration
- **Unique ID preservation**: Confirm default service maintains original unique ID format
- **`CALENDAR_YEAR_LOOKAROUND` constant**: Verify value is 3; verify `async_get_events` returns exactly `2 * CALENDAR_YEAR_LOOKAROUND + 1` annual occurrences over the full ±lookaround window
- **Integration lifecycle**: Verify `async_setup_entry` → `async_unload_entry` → `async_setup_entry` (reload) leaves entity state intact
- **Multi-service config entries**: Both calendars created, each shows only its own schedules, unique IDs assigned correctly, `default_configuration` is per-service
- **Holiday import error truncation**: When >3 holidays fail to import, error message ends with `" (and N more)"`

### Holiday Import Test Scenarios
- **Country Discovery**: Dynamic loading of 499+ countries from holidays library
- **Category Detection**: Dynamic category discovery per country (public, bank, school, etc.)
- **Pattern Analysis**: Fixed date vs variable date detection across multiple years
- **Conflict Resolution**: Name conflicts with overwrite/skip options
- **Date Overlap Handling**: Skip overlapping holidays based on flag setting
- **Country Name Flag**: Include/exclude country code in schedule names
- **Error Handling**: Graceful fallback when holidays library unavailable
- **Async Operations**: Non-blocking holiday data processing
- **Import Results**: Accurate reporting of imported/skipped/overwritten counts
- **Pattern Fallbacks**: Single-date holidays get appropriate fallback patterns
- **Error Truncation**: When all imports fail and >3 errors, message shows `"(and N more)"`

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
- Integration type: `service`
- Quality scale: Gold
- All-day events only (no time components)
- Proper error handling with translated messages
- Migration system for backward compatibility
- External dependencies: `holidays>=0.34` for holiday import functionality

### Code Quality
- Use constants from const.py for month/day/occurrence names
- Proper async/await patterns
- No blocking operations in event loop (use `run_in_executor` for holiday data processing)
- Clean separation of concerns (config flow, calendar, date generation, holiday import)
- Comprehensive error handling with graceful fallbacks
- Descriptive variable and function names
- Async-first design for all I/O operations

### Documentation
- Docstrings for all public functions
- Clear comments for complex logic
- README with setup and usage instructions
- SPEC.md (this document) for complete specification

## Success Criteria

The integration is complete when:
1. Users can create multiple scheduler services with unique names
2. Each service can have multiple schedules of all three types
3. Schedules can be added, edited, and removed without data loss
4. Configuration system works (default and per-schedule) with "Default Configuration" terminology
5. Calendar entities display correct events for all schedule types
6. **Calendar entity IDs are clean**: `calendar.{service_name}` format without duplication
7. Year-wrapping schedules work correctly
8. Overlap detection prevents conflicting schedules
9. All validation rules are enforced with clear error messages
10. Configuration YAML is properly displayed when editing schedules
11. Diagnostics feature provides comprehensive service-based troubleshooting data
12. Migration system seamlessly upgrades v1 to v2 without data loss or entity ID changes
13. All tests pass with >95% coverage (including migration, diagnostics, and entity ID tests)
14. Code passes linting and formatting checks
15. Integration loads and unloads cleanly in Home Assistant
16. Service-based architecture supports future enhancements
17. **Holiday Import**: Users can import holidays from 499+ countries with smart pattern detection
18. **Holiday Import Options**: Include country name flag, conflict resolution, and category selection work correctly
19. **UI Consistency**: All user-facing text uses "Default Configuration" not "Service Configuration"
20. **Entity Continuity**: Calendar entity IDs remain consistent before and after migration
