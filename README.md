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

1. Go to Settings -> Devices & Services
2. Click "+ Add Integration"
3. Search for "Scheduler"
4. Follow the configuration steps

## Features

- Easy configuration through the UI
- Schedule automation tasks based on date ranges or week patterns
- Binary sensors for each schedule that activate during configured periods
- Additional configuration for each sensor to provide schedule specific values
- Calendar integration showing all active schedules
- Hub device that aggregates all schedules

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
