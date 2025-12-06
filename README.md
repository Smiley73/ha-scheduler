# Scheduler for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/yourusername/ha-scheduler.svg)](https://github.com/yourusername/ha-scheduler/releases)
[![License](https://img.shields.io/github/license/yourusername/ha-scheduler.svg)](LICENSE)

A custom Home Assistant integration for scheduling automation tasks.

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
- Calendar integration showing all active schedules
- Hub device that aggregates all schedules
- Local polling for reliability

### Calendar Integration

The Scheduler integration automatically creates a calendar entity that displays all your schedules as calendar events. Each schedule appears as an all-day event on the days when it's active. This makes it easy to visualize your schedules in Home Assistant's calendar view.

The calendar entity is assigned to the Scheduler hub device and updates automatically when schedules are added, modified, or deleted.

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/yourusername/ha-scheduler/issues).

## License

This project is licensed under the MIT License - see the LICENSE file for details.
