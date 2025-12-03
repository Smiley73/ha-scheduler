# Development Guide

This guide will help you set up your development environment and run tests for the Scheduler integration.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setting Up Your Development Environment](#setting-up-your-development-environment)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Create a Virtual Environment](#2-create-a-virtual-environment)
  - [3. Install Dependencies](#3-install-dependencies)
- [Running Tests](#running-tests)
  - [Run All Tests](#run-all-tests)
  - [Run Tests with Verbose Output](#run-tests-with-verbose-output)
  - [Run Tests with Coverage Report](#run-tests-with-coverage-report)
  - [Run Tests with Detailed Coverage](#run-tests-with-detailed-coverage-shows-missing-lines)
  - [Run a Specific Test File](#run-a-specific-test-file)
  - [Run a Specific Test Function](#run-a-specific-test-function)
- [Code Quality Checks](#code-quality-checks)
  - [Run Linting with Ruff](#run-linting-with-ruff)
  - [Run Code Formatting with Black](#run-code-formatting-with-black)
  - [Run Import Sorting with isort](#run-import-sorting-with-isort)
- [Testing Locally in Home Assistant](#testing-locally-in-home-assistant)
  - [Method 1: Symlink (Recommended for Development)](#method-1-symlink-recommended-for-development)
  - [Method 2: Copy Files](#method-2-copy-files)
  - [Adding the Integration](#adding-the-integration)
- [Project Structure](#project-structure)
- [Debugging Tips](#debugging-tips)
  - [Enable Debug Logging](#enable-debug-logging)
  - [View Logs](#view-logs)
  - [Using pytest with pdb](#using-pytest-with-pdb)
- [Continuous Integration](#continuous-integration)
- [Making Changes](#making-changes)
- [Troubleshooting](#troubleshooting)
  - [Tests Fail with Import Errors](#tests-fail-with-import-errors)
  - [Home Assistant Doesn't Detect the Integration](#home-assistant-doesnt-detect-the-integration)
  - [Coverage Report Shows Missing Lines](#coverage-report-shows-missing-lines)
- [Resources](#resources)
- [Getting Help](#getting-help)

## Prerequisites

- Python 3.13
- Git
- A Home Assistant installation (for manual testing)

## Setting Up Your Development Environment

### 1. Clone the Repository

```bash
git clone https://github.com/Smiley73/ha-scheduler.git
cd ha-scheduler
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install test dependencies
pip install -r requirements_test.txt

# Install runtime dependencies
pip install -r requirements.txt
```

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run Tests with Verbose Output

```bash
pytest tests/ -v
```

### Run Tests with Coverage Report

```bash
pytest tests/ --cov=custom_components/scheduler --cov-report=term
```

### Run Tests with Detailed Coverage (shows missing lines)

```bash
pytest tests/ --cov=custom_components/scheduler --cov-report=term-missing
```

### Run a Specific Test File

```bash
pytest tests/test_config_flow.py -v
```

### Run a Specific Test Function

```bash
pytest tests/test_config_flow.py::test_form -v
```

## Code Quality Checks

### Run Linting with Ruff

```bash
ruff check custom_components/
```

### Run Code Formatting with Black

```bash
# Check formatting
black --check custom_components/

# Auto-format code
black custom_components/
```

### Run Import Sorting with isort

```bash
# Check import order
isort --check-only custom_components/

# Auto-sort imports
isort custom_components/
```

## Testing Locally in Home Assistant

### Method 1: Symlink (Recommended for Development)

1. Locate your Home Assistant configuration directory (usually `~/.homeassistant` or `/config`)

2. Create a symlink to your development directory:

```bash
ln -s /path/to/ha-scheduler/custom_components/scheduler ~/.homeassistant/custom_components/scheduler
```

3. Restart Home Assistant

### Method 2: Copy Files

1. Copy the integration to your Home Assistant custom_components directory:

```bash
cp -r custom_components/scheduler ~/.homeassistant/custom_components/
```

2. Restart Home Assistant after each change

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Scheduler"
4. Follow the configuration steps

## Project Structure

```
ha-scheduler/
├── custom_components/
│   └── scheduler/
│       ├── __init__.py          # Integration setup
│       ├── config_flow.py       # Configuration UI flow
│       ├── const.py             # Constants
│       ├── manifest.json        # Integration metadata
│       ├── strings.json         # UI translations
│       └── switch.py            # Switch platform
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Test fixtures
│   ├── test_config_flow.py      # Config flow tests
│   ├── test_init.py             # Integration setup tests
│   └── test_switch.py           # Switch platform tests
├── .github/
│   └── workflows/
│       ├── lint.yml             # Linting workflow
│       ├── test.yml             # Testing workflow
│       └── validate.yml         # HACS validation workflow
├── requirements.txt             # Runtime dependencies
├── requirements_test.txt        # Test dependencies
├── pytest.ini                   # Pytest configuration
├── hacs.json                    # HACS metadata
└── README.md                    # User documentation
```

## Debugging Tips

### Enable Debug Logging

Add to your Home Assistant `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.scheduler: debug
```

### View Logs

```bash
# Follow logs in real-time
tail -f ~/.homeassistant/home-assistant.log | grep scheduler
```

### Using pytest with pdb

Add breakpoints in your code:

```python
import pdb; pdb.set_trace()
```

Then run tests with:

```bash
pytest tests/ -s
```

## Continuous Integration

This project uses GitHub Actions for CI/CD:

- **Test Workflow**: Runs pytest with coverage on every push/PR
- **Lint Workflow**: Checks code quality with ruff, black, and isort
- **Validate Workflow**: Validates HACS and Home Assistant compliance

All workflows run on Python 3.13.

## Making Changes

1. Create a new branch for your feature/fix:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. Make your changes

3. Run tests to ensure everything works:
   ```bash
   pytest tests/ --cov=custom_components/scheduler
   ```

4. Run linting:
   ```bash
   ruff check custom_components/
   black --check custom_components/
   ```

5. Commit your changes:
   ```bash
   git add .
   git commit -m "Add my new feature"
   ```

6. Push and create a pull request:
   ```bash
   git push origin feature/my-new-feature
   ```

## Troubleshooting

### Tests Fail with Import Errors

Make sure you've installed all dependencies:
```bash
pip install -r requirements_test.txt
pip install -r requirements.txt
```

### Home Assistant Doesn't Detect the Integration

1. Ensure the integration is in the correct directory
2. Check that `manifest.json` is valid JSON
3. Restart Home Assistant completely
4. Check logs for any errors

### Coverage Report Shows Missing Lines

Run with detailed coverage to see which lines aren't covered:
```bash
pytest tests/ --cov=custom_components/scheduler --cov-report=term-missing
```

Then add tests to cover those lines.

## Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Documentation](https://hacs.xyz/)
- [pytest Documentation](https://docs.pytest.org/)
- [Home Assistant Custom Component Testing](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)

## Getting Help

- Open an issue on [GitHub](https://github.com/Smiley73/ha-scheduler/issues)
- Check existing issues for similar problems
- Provide logs and error messages when reporting issues
