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
- **Add Schedule**: Create a new schedule
- **Edit Schedule**: Modify an existing schedule's parameters
- **Rename Schedule**: Change a schedule's name
- **Remove Schedule**: Delete a schedule

The integration automatically prevents overlapping schedules to avoid conflicts.

## Features

- Easy configuration through the UI
- Three flexible schedule types: date-based, week-based, and nth-day
- Binary sensors for each schedule that activate during configured periods
- Additional configuration for each sensor to provide schedule specific values
- Calendar integration showing all active schedules
- Hub device that aggregates all schedules
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

The Scheduler integration automatically creates a calendar entity that displays all your schedules as calendar events. 

The calendar entity is assigned to the Scheduler hub device and updates automatically when schedules are added, modified, or deleted.

## Advanced Configuration

Each schedule allows to specify additional yaml configuration that can be access through the either the specific binary_sensor for the schedule or the aggregate one. The configuration is available through the `config` attribute.

The examples below "work on my machine" and are provided for reference only. Tweak it based on your needs.

#### Example Lighting for Christmas Schedule:

Add the below to the advanced configration for the schedule.

```
colors:
  - red
  - green
brightness:
  - 50
  - 20
```

#### Custom Sensor

A custom senor to change the light color and brightnes once every minute based on the provided list. Add this to your `templates.yaml`.

```
- sensor:
  - name: "Motion Lights Seasonal Color"
    unique_id: motion_lights_seasonal_color
    state: >
      {% if is_state('binary_sensor.scheduler', 'on') %}
        {% set colors = state_attr('binary_sensor.scheduler', 'config')['colors'] %}
      {% else %}
        {% set colors = ['yellow'] %}
      {% endif %}
      {{ colors[now().minute % (colors | length)] }}
    attributes:
        brightness_pct: >
          {% if is_state('binary_sensor.scheduler', 'on') %}
            {% set brightness = state_attr('binary_sensor.scheduler', 'config')['brightness'] %}
          {% else %}
            {% set brightness = [50] %}
          {% endif %}
          {{ brightness[now().minute % (brightness | length)] }}
```

#### Example automation to change lights

```
alias: Seasonal Lights
description: ""
triggers:
  - event: sunset
    offset: "-00:30:00"
    id: sunset
    trigger: sun
  - entity_id:
      - light.side_door_patio_light
      - light.front_porch_light
    to: "off"
    id: light_off
    trigger: state
  - entity_id:
      - sensor.motion_lights_seasonal_color
    id: colorchange
    from: null
    to: null
    for:
      hours: 0
      minutes: 0
      seconds: 1
    trigger: state
conditions:
  - condition: state
    entity_id: binary_sensor.scheduler
    state:
      - "on"
  - condition: state
    entity_id: input_boolean.seasonal_night_lights_enabled
    state: "on"
  - condition: sun
    before: sunrise
    after: sunset
    enabled: true
    before_offset: "+00:30:00"
    after_offset: "-00:30:00"
actions:
  - variables:
      color_name: |
        {{ states('sensor.motion_lights_seasonal_color') }}
      brightness_pct: |
        {{ state_attr('sensor.motion_lights_seasonal_color', 'brightness_pct')
        }}
      lights:
        - light.front_porch_light
        - light.side_door_patio_light
      motion_timers:
        - timer.front_porch_light
        - timer.side_door_patio_light
  - repeat:
      count: "{{ lights | count }}"
      sequence:
        - variables:
            light: |
              {{ lights[repeat.index - 1] }}
            motion_timer: |
              {{ motion_timers[repeat.index - 1] }}
        - if:
            - condition: template
              value_template: |
                {{ is_state (motion_timer, 'idle') }}
              alias: Motion light not active
            - alias: Light off or dim
              condition: or
              conditions:
                - condition: template
                  value_template: |
                    {{ is_state (light, 'off') }}
                - condition: template
                  value_template: |
                    {{ (state_attr(light, 'brightness') | int) <= 140}}
          then:
            - data:
                brightness_pct: 0
                transition: 1
              target:
                entity_id: "{{ light }}"
              action: light.turn_on
            - delay:
                hours: 0
                minutes: 0
                seconds: 0
                milliseconds: 500
            - data:
                color_name: "{{ color_name }}"
                brightness_pct: "{{ brightness_pct }}"
                transition: 1
              target:
                entity_id: "{{ light }}"
              action: light.turn_on
mode: single
```

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/Smiley73/ha-scheduler/issues).

## License

This project is licensed under the MIT License - see the LICENSE file for details.
