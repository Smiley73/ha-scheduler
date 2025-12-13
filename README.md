# Scheduler for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/Smiley73/ha-scheduler.svg)](https://github.com/Smiley73/ha-scheduler/releases)
[![License](https://img.shields.io/github/license/Smiley73/ha-scheduler.svg)](LICENSE)

A custom Home Assistant integration to support seasonal schedules, like holiday lighting.

## Table of Contents

- [⚠️ Breaking Change in v0.3.0](#️-breaking-change-in-v030)
- [Installation](#installation)
- [Configuration](#configuration)
- [Features](#features)
- [Schedule Types](#schedule-types)
- [Advanced Configuration](#advanced-configuration)
- [Diagnostics](#diagnostics)
- [Support](#support)
- [License](#license)

## ⚠️ Breaking Change in v0.3.0

**Important:** Version 0.3.0 introduces a breaking change. The Home Assistant domain has been renamed from `scheduler` to `ha_scheduler`. This change was necessary to avoid conflicts with other integrations.

**Migration Required:**
1. **Remove the old integration** from Settings → Devices & Services before updating
2. **Reinstall** the integration after updating to v0.3.0
3. **Recreate all schedules** - your previous schedules will not be migrated automatically

We apologize for the inconvenience, but this change ensures better compatibility and follows Home Assistant naming conventions.

> **Note:** The majority of this code was generated with AI assistance using [Kiro](https://kiro.dev), an AI-powered IDE designed for developers. Kiro combines intelligent code generation with deep integration understanding to accelerate development while maintaining code quality.

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
2. Click the "Helpers" tab
3. Click "+ Create Helper" and select "Scheduler"
4. Provide a name for the scheduler and click "Submit" to create it

### Adding Schedules

1. Go to Settings -> Devices & Services
2. Click the "Helpers" tab
3. Find the "Scheduler" helper and open it by clicking on it
4. Click the "Settings" icon (gear symbol in the upper right corner)
5. Select "Scheduler Options"
6. Select "Add Schedule"
7. Enter a name and choose a schedule type (Date, Week, or Nth-Day)
8. Configure the schedule parameters based on the type selected
9. (Optional) Add YAML configuration for custom attributes

### Managing Schedules

From the Configure menu, you can:
- **Add Schedule**: Create a new schedule with optional configuration
- **Remove Schedule**: Delete an existing schedule
- **Edit Default Configuration**: Set default configuration that applies to all schedules

The integration automatically prevents overlapping schedules to avoid conflicts.

## Features

- Easy configuration through the UI
- Three flexible schedule types: date-based, week-based, and nth-day
- Calendar entity showing all active schedules as events
- Optional YAML configuration per schedule for custom attributes
- Default configuration that applies to all schedules
- Automatic overlap detection to prevent conflicting schedules

## Schedule Types

The Scheduler integration supports three types of schedules to cover different use cases:

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

**Use for:** Schedules based on specific weeks within months, like "first week of every month" or "last two weeks of December."

**Configuration:**
- Start Month, Week (0-4), and Day of Week: When the schedule begins
- End Month, Week (0-4), and Day of Week: When the schedule ends
- Week 0 = first week, Week 4 = last week

**Examples:**
- First Monday of every month: Week 0, Monday to Week 0, Monday
- Last week of December: Week 4, Monday to Week 4, Sunday
- Mid-month period: Week 2, Monday to Week 3, Friday

**Note:** All days between the start and end dates are active, not just the specified days of the week.

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

The Scheduler integration creates a calendar entity (`calendar.<scheduler_name>`) that displays all your schedules as calendar events. Each schedule appears as an event during its active period, making it easy to visualize your schedules in Home Assistant's calendar view.

**Calendar Features:**
- Automatically updates when schedules are added, modified, or deleted
- Shows the current active event (if any) in the calendar entity state
- Configuration data available through dedicated entity attributes
- Events span the full duration of each schedule period
- Supports year-wrapping schedules (e.g., November to February)

**Using the Calendar:**
- View in the Calendar dashboard
- Use `calendar.get_events` service to query upcoming schedules
- Access the current event via `calendar.<scheduler_name>.event`
- If a schedule is active `calendar.<scheduler_name>` will have the state `on`
- Access configuration via `state_attr('calendar.<scheduler_name>', 'configuration')`

## Advanced Configuration

### Schedule-Specific Configuration

Each schedule can have optional YAML configuration that provides custom attributes for that schedule. This configuration is included in the calendar event's description field.

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

The configuration is available through dedicated attributes on the calendar entity when a schedule is active. This provides clean, direct access to schedule-specific settings in your automations.

**Available Calendar Attributes:**
- `configuration`: Current active schedule's configuration (or default if none active)
- `name`: Name of the currently active schedule
- `schedule_uid`: Unique identifier of the active schedule
- `default_configuration`: Default configuration from integration settings

**Check if a schedule is currently active:**

```yaml
condition: template
value_template: "{{ state_attr('calendar.my_scheduler', 'name') != None }}"
```

**Access configuration directly from the calendar entity:**

When a schedule is active, the `configuration` attribute contains the schedule's configuration dict (or the default configuration if the schedule doesn't have its own):

```yaml
variables:
  # Get configuration from the active schedule
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

### Tips for Using Configuration

1. **Keep it simple**: Store only the values you need (colors, temperatures, modes, etc.)
2. **Use defaults**: Always provide default values in templates with `| default(value)`
3. **Test your YAML**: Invalid YAML in the configuration field will prevent the schedule from saving
4. **Access nested values**: Use dot notation or bracket notation: `config.settings.brightness` or `config['settings']['brightness']`
5. **Default configuration**: Set common values in the default configuration, override per schedule as needed

## Diagnostics

The Scheduler integration provides comprehensive diagnostic information to help troubleshoot issues and understand your schedule configuration. The diagnostics include detailed information about each schedule, future date calculations, overlap detection, and more.

### How to Generate Diagnostics

1. **Via Home Assistant UI:**
   - Go to Settings → Devices & Services
   - Find your Scheduler integration
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
