# Scheduler for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/Smiley73/ha-scheduler.svg)](https://github.com/Smiley73/ha-scheduler/releases)
[![License](https://img.shields.io/github/license/Smiley73/ha-scheduler.svg)](LICENSE)

A custom Home Assistant integration to support seasonal schedules, like holiday lighting.

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

1. Copy the `custom_components/scheduler` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to Settings -> Devices & Services
2. Click "+ Add Integration"
3. Search for "Scheduler"
4. Click "Submit" to create the Scheduler hub

### Adding Schedules

1. Go to Settings -> Devices & Services
2. Find the "Scheduler" integration
3. Click "Configure"
4. Select "Add Schedule"
5. Enter a name and choose a schedule type (Date, Week, or Nth-Day)
6. Configure the schedule parameters based on the type selected
7. (Optional) Add YAML configuration for custom attributes

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
- Each event includes the schedule name and optional configuration in the description
- Events span the full duration of each schedule period
- Supports year-wrapping schedules (e.g., November to February)

**Using the Calendar:**
- View in the Calendar dashboard
- Use `calendar.get_events` service to query upcoming schedules
- Access the current event via `calendar.<scheduler_name>.event`
- Check if a schedule is active: `state_attr('calendar.<scheduler_name>', 'message')` will show the current event name

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

The configuration is available in the `description` attribute on the calendar entity when a schedule is active. This makes it easy to access schedule-specific settings in your automations.

**Check if a schedule is currently active:**

```yaml
condition: template
value_template: "{{ state_attr('calendar.my_scheduler', 'message') != None }}"
```

**Access configuration directly from the calendar entity:**

When a schedule is active, the `description` attribute contains the schedule's configuration dict (or the default configuration if the schedule doesn't have its own):

```yaml
variables:
  # Get configuration from the active schedule
  config: "{{ state_attr('calendar.my_scheduler', 'description') | default({}) }}"
  color: "{{ config.color | default('white') }}"
  brightness: "{{ config.brightness | default(50) }}"
```

**Alternative: Use calendar.get_events service:**

You can also get configuration via the calendar.get_events service:

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
    config: "{{ current_event.description if current_event else {} }}"
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
    attribute: message
conditions:
  - condition: template
    value_template: "{{ state_attr('calendar.holiday_scheduler', 'message') != None }}"
  - condition: sun
    after: sunset
    before: sunrise
actions:
  - variables:
      # Get configuration from the active schedule
      config: "{{ state_attr('calendar.holiday_scheduler', 'description') | default({}) }}"
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
    attribute: message
conditions:
  - condition: template
    value_template: "{{ state_attr('calendar.holiday_scheduler', 'message') != None }}"
  - condition: sun
    after: sunset
    before: sunrise
actions:
  - variables:
      config: "{{ state_attr('calendar.holiday_scheduler', 'description') | default({}) }}"
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
    attribute: message
  - platform: homeassistant
    event: start
conditions:
  - condition: template
    value_template: "{{ state_attr('calendar.thermostat_scheduler', 'message') != None }}"
actions:
  - variables:
      config: "{{ state_attr('calendar.thermostat_scheduler', 'description') | default({}) }}"
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
    attribute: message
actions:
  - variables:
      schedule_name: "{{ state_attr('calendar.my_scheduler', 'message') }}"
      config: "{{ state_attr('calendar.my_scheduler', 'description') | default({}) }}"
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
```

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/Smiley73/ha-scheduler/issues).

## License

This project is licensed under the MIT License - see the LICENSE file for details.
