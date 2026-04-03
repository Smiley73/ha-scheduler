# Scheduler for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/Smiley73/ha-scheduler.svg)](https://github.com/Smiley73/ha-scheduler/releases)
[![License](https://img.shields.io/github/license/Smiley73/ha-scheduler.svg)](LICENSE)

A custom Home Assistant integration to support seasonal schedules, like holiday lighting.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
  - [Holiday Import Feature](#holiday-import-feature)
- [Features](#features)
- [Schedule Types](#schedule-types)
- [Advanced Configuration](#advanced-configuration)
  - [Enhanced Week Schedule Examples](#enhanced-week-schedule-examples)
- [Diagnostics](#diagnostics)
- [Support](#support)
- [License](#license)

> **Note:** The majority of this code was generated with AI assistance using [Kiro](https://kiro.dev) and [Claude Code](https://claude.ai).

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL and select "Integration" as the category
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/ha_scheduler` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to Settings -> Devices & Services
2. Click "+ Add Integration"
3. Search for "HA Scheduler" and select it
4. Provide a name for the scheduler and click "Submit" to create it

### Adding Schedules

1. Go to Settings -> Devices & Services
2. Find the "HA Scheduler" integration and click "Configure"
3. Select "Add Schedule"
4. Enter a name and choose a schedule type (Date, Week, or Nth-Day)
5. Configure the schedule parameters based on the type selected
6. (Optional) Add YAML configuration for custom attributes

### Managing Schedules

From the Configure menu, you can:
- **Add Schedule**: Create a new schedule with optional configuration
- **Remove Schedule**: Delete an existing schedule
- **Import Holidays**: Import holidays from any supported country as schedules
- **Edit Default Configuration**: Set default configuration that applies to all schedules

The integration automatically prevents overlapping schedules to avoid conflicts.

### Holiday Import Feature

The HA Scheduler integration includes a powerful holiday import feature that allows you to automatically create schedules for holidays from any supported country using the Python `holidays` library.

#### How to Import Holidays

1. Go to Settings → Devices & Services
2. Find your HA Scheduler integration and click "Configure"
3. Select "Import Holidays"
4. **Step 1**: Choose a country from the extensive list of available options (e.g., US, CA, GB, DE, FR, AU, etc.)
5. **Step 2**: Select holiday categories available for that country (Public, Bank, School, Observance, etc.)
6. **Step 3**: Choose specific holidays and configure import options:
   - **Holidays to import**: Select from the list with automatically detected pattern descriptions
   - **Overwrite existing**: Replace schedules with the same name
   - **Skip on overlap**: Skip holidays that would conflict with existing schedules, including replacements when overwrite is enabled
   - **Include country name**: Add country code to schedule names (e.g., "Independence Day (USA)" vs "Independence Day")

#### Smart Pattern Detection

The holiday import feature automatically analyzes multiple years of holiday data to determine the best schedule type:

- **Fixed Date Holidays** (e.g., Independence Day - July 4th, Christmas - December 25th)
  - Creates "Date" type schedules with the same date every year
  - Pattern: `Fixed date: July 04`

- **Variable Date Holidays** (e.g., Martin Luther King Jr. Day - 3rd Monday in January)
  - Creates "Nth-Day" type schedules that automatically adjust each year
  - Pattern: `Third Monday of January`

- **Multi-Day Holidays** (e.g., Easter weekend spanning multiple days)
  - Creates "Week" type schedules for holidays that span consecutive days within the same week
  - Pattern: `First week of April (Friday to Monday)` (example)

- **Complex Variable Holidays** (e.g., Thanksgiving - 4th Thursday in November)
  - Automatically calculates the correct occurrence and weekday
  - Pattern: `Fourth Thursday of November`

- **Fallback Handling**: For holidays with unpredictable patterns, creates single-date schedules using a representative year

#### Supported Countries and Categories

- **Countries**: Extensive support through the Python `holidays` library including:
  - **Major countries**: US, Canada, UK, Germany, France, Australia, New Zealand, Japan, South Korea
  - **European Union**: All EU member states with country-specific holidays
  - **Americas**: North, Central, and South American countries
  - **Asia-Pacific**: Most Asian and Pacific region countries
  - **Africa & Middle East**: Many African and Middle Eastern countries

- **Categories** (varies by country):
  - **Public**: National/federal holidays and official observances
  - **Bank**: Banking and financial sector holidays
  - **School**: Educational institution holidays and breaks
  - **Observance**: Cultural, religious, and traditional observances
  - **Optional**: Regional or optional holidays
  - **Government**: Government office closures
  - **Financial**: Financial market holidays

#### Pattern Analysis Process

The import feature analyzes 3 years of holiday data (2023-2025) to detect patterns:

1. **Data Collection**: Retrieves holiday dates for multiple years
2. **Pattern Recognition**: Analyzes date consistency and variations
3. **Schedule Type Selection**: Chooses the most appropriate schedule type
4. **Validation**: Ensures patterns work correctly across years

#### Conflict Management

The import feature includes comprehensive conflict detection:

- **Name Conflicts**: Option to overwrite existing schedules with identical names
- **Date Overlaps**: Option to skip holidays that would conflict with existing schedule periods
- **Clear Feedback**: Detailed reporting of what was imported, skipped, or overwritten
- **Preview Mode**: See what would be imported before making changes

#### Examples

**Import US Federal Holidays:**
1. Select "United States" → "Public" → Choose holidays like:
   - Independence Day → `Fixed date: July 04`
   - Thanksgiving → `Fourth Thursday of November`
   - Martin Luther King Jr. Day → `Third Monday of January`
   - Memorial Day → `Last Monday of May`

**Import UK Bank Holidays:**
1. Select "United Kingdom" → "Bank" → Choose holidays like:
   - Christmas Day → `Fixed date: December 25`
   - Easter Monday → `Variable date pattern`
   - Spring Bank Holiday → `Last Monday of May`
   - Summer Bank Holiday → `Last Monday of August`

**Import German Public Holidays:**
1. Select "Germany" → "Public" → Choose holidays like:
   - German Unity Day → `Fixed date: October 03`
   - Easter Monday → `Variable date pattern`
   - Christmas Day → `Fixed date: December 25`

**Import Canadian Holidays:**
1. Select "Canada" → "Public" → Choose holidays like:
   - Canada Day → `Fixed date: July 01`
   - Thanksgiving → `Second Monday of October`
   - Victoria Day → `Third Monday of May`

## Features

- Easy configuration through the UI
- Three flexible schedule types: date-based, week-based, and nth-day
- **Enhanced week-based schedules** with optional day restrictions, country-specific week starts, and partial/full week types
- **Holiday import feature** supporting 100+ countries with automatic pattern detection
- Calendar entity showing all active schedules as events
- Optional YAML configuration per schedule for custom attributes
- Default configuration that applies to all schedules
- Automatic overlap detection to prevent conflicting schedules

## Schedule Types

The HA Scheduler integration supports three types of schedules to cover different use cases:

### 1. Date-Based Schedules

**Use for:** Fixed date ranges like holiday seasons, summer months, or specific date periods.

**Configuration:**
- Start Month & Day: When the schedule begins (e.g., November 15)
- End Month & Day: When the schedule ends (e.g., January 10)

**Examples:**
- Christmas lights: November 25 - January 6
- Summer pool schedule: June 1 - August 31
- Tax season reminder: February 1 - April 15

**Supports wrap-around:** Yes (e.g., November to February crosses year boundary)

### 2. Week-Based Schedules

**Use for:** Schedules based on specific weeks within months, like "first week of every month," "last two weeks of December," or entire weeks without specific day restrictions.

**Enhanced Configuration Options:**
- **Start Month & Week (0-4)**: When the schedule begins (Week 0 = first week, Week 4 = last week)
- **End Month & Week (0-4)**: When the schedule ends
- **Day of Week (Optional)**: Specific days within the week range
- **Week Type**: How first/last weeks are calculated
- **Country Code**: Determines week start day (Sunday vs Monday)

**Week Types:**
- **Partial** (default): First week includes any days in the month, even if week starts in previous month
- **Full**: First week must be entirely within the month

**Day of Week Options:**
- **Both days specified**: Traditional behavior - specific day range (e.g., Monday to Friday)
- **Start day only**: From specified day to end of week period
- **End day only**: From start of week period to specified day  
- **No days specified**: Entire week(s) are active

**Country-Specific Week Starts:**
- **Sunday-first countries**: US, CA, JP, KR, and many others
- **Monday-first countries**: Most of Europe, AU, NZ (default)

**Examples:**
- **Entire first week of every month**: Week 0 to Week 0 (no day restrictions)
- **First Monday of every month**: Week 0, Monday to Week 0, Monday
- **Last week of December**: Week 4, Monday to Week 4, Sunday  
- **Mid-month period**: Week 2, Monday to Week 3, Friday
- **Whole weeks 2-3**: Week 1 to Week 2 (no day restrictions)
- **US-style first full week**: Week 0, Week Type: Full, Country: US

**Note:** All days between the start and end dates are active, not just the specified days of the week.

**Validation:** Week-based schedules that do not produce a valid recurring range are rejected during configuration. For example, choosing a start day later than the end day within the same week, or selecting a weekday that does not exist in the chosen partial week pattern, will not be saved.

### 3. Nth-Day Schedules

**Use for:** Schedules around specific occurrences of weekdays in a month, like "Thanksgiving" or "second Tuesday of March."

**Configuration:**
- Month: Target month (1-12)
- Occurrence: Which occurrence (First, Second, Third, Fourth, or Last)
- Day of Week: Target weekday (Monday-Sunday)
- Start Offset: Days before the target date to activate (0-30)
- End Offset: Days after the target date to stay active (0-30)

**Examples:**
- Thanksgiving (4th Thursday of November): Month=11, Occurrence=Fourth, Day=Thursday, Offsets=0/0
- Mother's Day weekend (2nd Sunday of May, Friday-Monday): Month=5, Occurrence=Second, Day=Sunday, Start Offset=2, End Offset=1
- Memorial Day (Last Monday of May): Month=5, Occurrence=Last, Day=Monday, Offsets=0/0
- Tax deadline prep (around April 15): Calculate 3rd Monday of April with appropriate offsets

**Perfect for:** US holidays, recurring events based on "nth weekday of month" patterns, and creating date ranges around specific days.

### Calendar Integration

The HA Scheduler integration creates a calendar entity (`calendar.<scheduler_name>`) that displays all your schedules as calendar events. Each schedule appears as an event during its active period, making it easy to visualize your schedules in Home Assistant's calendar view.

**Calendar Features:**
- Automatically updates when schedules are added, modified, or deleted
- Exposes the active event, or the next upcoming event when the calendar is idle
- Configuration data available through dedicated entity attributes
- Events span the full duration of each schedule period
- Supports year-wrapping schedules (e.g., November to February)

**Using the Calendar:**
- View in the Calendar dashboard
- Use `calendar.get_events` service to query upcoming schedules
- Access the active or next upcoming event via `calendar.<scheduler_name>.event`
- If a schedule is active `calendar.<scheduler_name>` will have the state `on`
- Access configuration via `state_attr('calendar.<scheduler_name>', 'configuration')`
- If there is no active or upcoming event, `calendar.<scheduler_name>.event` is `None`, the calendar state stays `off`, `name` and `schedule_uid` are `None`, and `configuration` falls back to the default configuration

## Advanced Configuration

### Schedule-Specific Configuration

Each schedule can have optional YAML configuration that provides custom attributes for that schedule. This configuration is exposed through the calendar entity attributes for the active schedule, or for the next upcoming schedule when the calendar is idle.

**Example: Christmas Lighting Schedule**

When adding a schedule, you can include configuration like:

```yaml
colors:
  - red
  - green
brightness: 50
effect: twinkle
```

### Default Configuration

You can also set a default configuration that applies to all schedules that don't have their own configuration. Access this from the Configure menu -> "Edit Default Configuration".

**Example Default Configuration:**

```yaml
mode: normal
brightness: 75
```

### Accessing Configuration in Automations

The configuration is available through dedicated attributes on the calendar entity for the active schedule, or for the next upcoming schedule when the calendar is idle. This provides clean, direct access to schedule-specific settings in your automations.

**Available Calendar Attributes:**
- `configuration`: Active schedule's configuration, or the next upcoming schedule's configuration (falls back to the default configuration if no schedule-specific config exists)
- `name`: Name of the currently active schedule, or the next upcoming schedule
- `schedule_uid`: Unique identifier of the active schedule, or the next upcoming schedule
- `default_configuration`: Default configuration from integration settings

If there is no active or upcoming schedule, `configuration` falls back to `default_configuration`, and `name` / `schedule_uid` are `None`.

**Check if a schedule is currently active:**

```yaml
condition: template
value_template: "{{ state_attr('calendar.my_scheduler', 'name') != None }}"
```

**Access configuration directly from the calendar entity:**

When a schedule is active, or when there is a next upcoming schedule, the `configuration` attribute contains that schedule's configuration dict (or the default configuration if the schedule doesn't have its own):

```yaml
variables:
  # Get configuration from the active or next upcoming schedule
  config: "{{ state_attr('calendar.my_scheduler', 'configuration') | default({}) }}"
  color: "{{ config.color | default('white') }}"
  brightness: "{{ config.brightness | default(50) }}"
  schedule_name: "{{ state_attr('calendar.my_scheduler', 'name') }}"
```

**Alternative: Use calendar.get_events service:**

You can also get events via the calendar.get_events service (note: configuration is in entity attributes, not event descriptions):

```yaml
- service: calendar.get_events
  target:
    entity_id: calendar.my_scheduler
  data:
    duration:
      hours: 1
  response_variable: schedule_events
- variables:
    current_event: "{{ schedule_events['calendar.my_scheduler'].events[0] if schedule_events['calendar.my_scheduler'].events else none }}"
    # Configuration comes from entity attributes, not event description
    config: "{{ state_attr('calendar.my_scheduler', 'configuration') | default({}) }}"
```

### Example 1: Multiple Holiday Schedules with Configuration

**Setup: Create schedules with specific configurations**

1. **Christmas Schedule** (Nov 25 - Jan 6):
```yaml
color: red
brightness: 75
effect: twinkle
```

2. **Halloween Schedule** (Oct 25 - Oct 31):
```yaml
color: orange
brightness: 100
effect: flash
```

3. **Summer Schedule** (Jun 1 - Aug 31):
```yaml
color: blue
brightness: 50
effect: none
```

**Automation: Apply schedule configuration to lights**

```yaml
alias: Seasonal Lights
description: "Automatically adjust lights based on active schedule configuration"
triggers:
  - platform: sun
    event: sunset
    offset: "-00:30:00"
  - platform: state
    entity_id: calendar.holiday_scheduler
    attribute: name
conditions:
  - condition: state
    entity_id: calendar.holiday_scheduler
    state:
      - "on"
  - condition: sun
    after: sunset
    before: sunrise
actions:
  - variables:
      # Get configuration from the active schedule
      config: "{{ state_attr('calendar.holiday_scheduler', 'configuration') | default({}) }}"
      color: "{{ config.color | default('white') }}"
      brightness: "{{ config.brightness | default(50) }}"
      effect: "{{ config.effect | default('none') }}"
  - service: light.turn_on
    target:
      entity_id: 
        - light.front_porch
        - light.back_yard
    data:
      color_name: "{{ color }}"
      brightness_pct: "{{ brightness }}"
      effect: "{{ effect }}"
mode: restart
```

### Example 2: Dynamic Color Rotation

**Schedule Configuration:**

```yaml
colors:
  - red
  - green
  - white
brightness: 60
change_interval: 300  # seconds
```

**Template Sensor** (add to `configuration.yaml`):

Note: Template sensors cannot directly call services, so for dynamic color rotation, use an automation that updates an input_select or helper entity based on the schedule configuration.

**Automation for color rotation:**

```yaml
alias: Rotate Holiday Colors
triggers:
  - platform: time_pattern
    minutes: "/5"  # Every 5 minutes
  - platform: state
    entity_id: calendar.holiday_scheduler
    attribute: name
conditions:
  - condition: state
    entity_id: calendar.holiday_scheduler
    state:
      - "on"
  - condition: sun
    after: sunset
    before: sunrise
actions:
  - variables:
      config: "{{ state_attr('calendar.holiday_scheduler', 'configuration') | default({}) }}"
      colors: "{{ config.colors | default(['white']) }}"
      interval: "{{ config.change_interval | default(300) }}"
      index: "{{ (now().timestamp() // interval) | int % (colors | length) }}"
      current_color: "{{ colors[index] }}"
      brightness: "{{ config.brightness | default(50) }}"
  - service: light.turn_on
    target:
      entity_id: light.front_porch
    data:
      color_name: "{{ current_color }}"
      brightness_pct: "{{ brightness }}"
mode: restart
```

### Example 3: Thermostat Schedule with Temperature Settings

**Setup: Create seasonal thermostat schedules**

1. **Winter Schedule** (Nov 1 - Mar 31):
```yaml
heat_temp: 70
cool_temp: 78
mode: heat
```

2. **Summer Schedule** (Jun 1 - Aug 31):
```yaml
heat_temp: 68
cool_temp: 74
mode: cool
```

3. **Spring/Fall Schedule** (Apr 1 - May 31, Sep 1 - Oct 31):
```yaml
heat_temp: 68
cool_temp: 76
mode: auto
```

**Automation: Apply thermostat settings**

```yaml
alias: Seasonal Thermostat
description: "Adjust thermostat based on seasonal schedule"
triggers:
  - platform: state
    entity_id: calendar.thermostat_scheduler
    attribute: name
  - platform: homeassistant
    event: start
conditions:
  - condition: state
    entity_id: calendar.thermostat_scheduler
    state:
      - "on"
actions:
  - variables:
      config: "{{ state_attr('calendar.thermostat_scheduler', 'configuration') | default({}) }}"
  - service: climate.set_temperature
    target:
      entity_id: climate.main_thermostat
    data:
      temperature: "{{ config.heat_temp }}"
      target_temp_high: "{{ config.cool_temp }}"
      target_temp_low: "{{ config.heat_temp }}"
      hvac_mode: "{{ config.mode }}"
mode: restart
```

### Example 4: Schedule Change Notifications

Get notified when schedules change with details about the new configuration:

```yaml
alias: Schedule Change Notification
triggers:
  - platform: state
    entity_id: calendar.my_scheduler
    attribute: name
actions:
  - variables:
      schedule_name: "{{ state_attr('calendar.my_scheduler', 'name') }}"
      config: "{{ state_attr('calendar.my_scheduler', 'configuration') | default({}) }}"
  - service: notify.mobile_app
    data:
      title: "Schedule Changed"
      message: >
        Now active: {{ schedule_name }}
        {% if config %}
        Settings: {{ config | tojson }}
        {% endif %}
mode: restart
```

### Enhanced Week Schedule Examples

The enhanced week-based schedules support flexible configurations for different use cases:

#### Example 1: Whole Week Schedules

**Monthly Deep Cleaning (First Full Week):**
```yaml
# Schedule Configuration
Schedule Type: Week
Start: Month 1, Week 0 (First), Week Type: Full
End: Month 12, Week 0 (First), Week Type: Full
Country: US  # Sunday-first weeks
# No day restrictions - entire week is active
```

**Vacation Weeks (Last Two Weeks of July):**
```yaml
Schedule Type: Week  
Start: Month 7, Week 2 (Third)
End: Month 7, Week 4 (Last)
# Covers two complete weeks
```

#### Example 2: Partial Week Schedules

**Weekend Maintenance (Saturday-Sunday of Second Week):**
```yaml
Schedule Type: Week
Start: Month 1, Week 1 (Second), Day: Saturday
End: Month 12, Week 1 (Second), Day: Sunday
# Repeats every month, second weekend
```

**Mid-Week Break (Wednesday to Friday of Third Week):**
```yaml
Schedule Type: Week
Start: Month 1, Week 2 (Third), Day: Wednesday  
End: Month 12, Week 2 (Third), Day: Friday
```

#### Example 3: Country-Specific Week Calculations

**US Business Week (Monday-Friday, First Full Week):**
```yaml
Schedule Type: Week
Start: Month 1, Week 0, Day: Monday, Week Type: Full
End: Month 12, Week 0, Day: Friday, Week Type: Full
Country: US
# First full business week using US Sunday-first calendar
```

**European Work Schedule (Monday-Thursday, First Week):**
```yaml
Schedule Type: Week
Start: Month 1, Week 0, Day: Monday, Week Type: Partial
End: Month 12, Week 0, Day: Thursday, Week Type: Partial  
Country: DE
# First week using European Monday-first calendar
```

#### Example 4: Flexible Day Specifications

**Start of Week Only (Monday to End of Week):**
```yaml
Schedule Type: Week
Start: Month 1, Week 0, Day: Monday
End: Month 12, Week 0
# From Monday through end of first week (Sunday in US, Sunday in Europe)
```

**End of Week Only (Start of Week to Friday):**
```yaml
Schedule Type: Week
Start: Month 1, Week 0
End: Month 12, Week 0, Day: Friday
# From start of first week through Friday
```

### Tips for Using Configuration

1. **Keep it simple**: Store only the values you need (colors, temperatures, modes, etc.)
2. **Use defaults**: Always provide default values in templates with `| default(value)`
3. **Test your YAML**: Invalid YAML in the configuration field will prevent the schedule from saving
4. **Access nested values**: Use dot notation or bracket notation: `config.settings.brightness` or `config['settings']['brightness']`
5. **Default configuration**: Set common values in the default configuration, override per schedule as needed
6. **Week schedules**: Use country codes for proper week start calculations (US=Sunday-first, most others=Monday-first)
7. **Week types**: Use "full" for schedules that must be entirely within the month, "partial" for flexibility

## Diagnostics

The HA Scheduler integration provides comprehensive diagnostic information to help troubleshoot issues and understand your schedule configuration. The diagnostics include detailed information about each schedule, future date calculations, overlap detection, and more.

### How to Generate Diagnostics

1. **Via Home Assistant UI:**
   - Go to Settings → Devices & Services
   - Find your HA Scheduler integration
   - Click on the integration name
   - Click the three dots menu (⋮) in the top right
   - Select "Download diagnostics"
   - Save the JSON file to your computer

2. **Via Developer Tools:**
   - Go to Developer Tools → Services
   - Select service: `system_log.write`
   - In the service data, use:
     ```yaml
     message: "Scheduler diagnostics requested"
     level: info
     ```
   - Then access diagnostics through the integration page as described above

### What Diagnostics Provide

The diagnostic output includes comprehensive information for troubleshooting and analysis:

#### Schedule Information
- **Basic Details**: Schedule ID, name, type, and configuration parameters
- **Day Names**: Human-readable day names alongside numeric values (e.g., "Monday" for day 0)
- **Configuration Status**: Whether each schedule has custom configuration or uses defaults

#### Future Date Calculations (Next 3 Years)
For each schedule, diagnostics calculate and display:
- **Start and End Dates**: Exact dates when each schedule will be active
- **Duration**: Number of days each schedule spans
- **Year-by-Year Breakdown**: Separate calculations for each of the next 3 years
- **Error Handling**: Clear error messages if date calculation fails for any year

#### Overlap Detection
Advanced conflict analysis for each year:
- **Conflict Status**: 
  - `"no_conflicts"`: No overlapping schedules found
  - `"conflicts_found"`: One or more overlapping schedules detected
  - `"no_dates"`: Schedule has no valid dates for the year
  - `"error"`: Error occurred during overlap detection

- **Detailed Conflict Information** (when conflicts exist):
  - Names and IDs of conflicting schedules
  - Exact start and end dates of conflicting schedules
  - Precise overlap periods (when conflicts actually occur)
  - Conflict count for schedules with multiple overlaps

#### Configuration Analysis
- **Default Configuration**: Shows if default configuration is set and its contents
- **Schedule-Specific Configuration**: Individual configuration for each schedule
- **Configuration Inheritance**: How schedules inherit from default configuration

### Example Diagnostic Output

```json
{
  "schedules": {
    "count": 2,
    "items": [
      {
        "id": "christmas-lights",
        "name": "Christmas Lights",
        "type": "date",
        "start_month": 11,
        "start_day": 25,
        "end_month": 1,
        "end_day": 6,
        "has_configuration": true,
        "future_dates": {
          "years": {
            "2025": {
              "start_date": "2025-11-25",
              "end_date": "2026-01-06",
              "duration_days": 43,
              "overlaps": {
                "status": "no_conflicts",
                "conflicting_schedules": [],
                "conflict_count": 0
              }
            }
          },
          "warnings": []
        }
      }
    ]
  }
}
```

### Using Diagnostics for Troubleshooting

**Common Issues Diagnostics Help Identify:**

1. **Schedule Overlaps**: Quickly identify which schedules conflict and during which periods
2. **Invalid Dates**: See which schedules fail to generate valid dates and why
3. **Configuration Problems**: Verify that schedule configurations are properly set
4. **Year Boundary Issues**: Check how schedules behave across year transitions
5. **Nth-Day Variations**: Understand how nth-day schedules (like Thanksgiving) shift across years

**When to Use Diagnostics:**
- Schedules not activating as expected
- Suspected overlapping schedules causing conflicts
- Verifying future schedule dates before important events
- Debugging configuration inheritance issues
- Preparing for year transitions (December to January schedules)

**Sharing Diagnostics:**
When reporting issues, include the diagnostic output (with sensitive information removed) to help maintainers understand your configuration and identify problems quickly.

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/Smiley73/ha-scheduler/issues).

## License

This project is licensed under the MIT License - see the LICENSE file for details.
