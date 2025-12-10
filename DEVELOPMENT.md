# Development Guide

This guide will help you set up your development environment and run tests for the Scheduler integration.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Setting Up Your Development Environment](#setting-up-your-development-environment)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Create a Virtual Environment](#2-create-a-virtual-environment)
  - [3. Install Dependencies](#3-install-dependencies)
  - [4. Install Pre-commit Hooks](#4-install-pre-commit-hooks)
- [Running Tests](#running-tests)
  - [Run All Tests](#run-all-tests)
  - [Run Tests with Verbose Output](#run-tests-with-verbose-output)
  - [Run Tests with Coverage Report](#run-tests-with-coverage-report)
  - [Run Tests with Detailed Coverage](#run-tests-with-detailed-coverage-shows-missing-lines)
  - [Run a Specific Test File](#run-a-specific-test-file)
  - [Run a Specific Test Function](#run-a-specific-test-function)
- [Code Quality Checks](#code-quality-checks)
  - [Pre-commit Hooks](#pre-commit-hooks)
  - [Run Linting with Ruff](#run-linting-with-ruff)
  - [Run Code Formatting with Ruff](#run-code-formatting-with-ruff)
  - [Manual Pre-commit Check](#manual-pre-commit-check)
- [Running Home Assistant Locally](#running-home-assistant-locally)
  - [Option 1: Local Development Instance (Recommended)](#option-1-local-development-instance-recommended)
  - [Option 2: Using Existing Home Assistant Installation](#option-2-using-existing-home-assistant-installation)
  - [Adding the Integration](#adding-the-integration)
  - [Hot Reloading During Development](#hot-reloading-during-development)
- [Debugging Tips](#debugging-tips)
  - [Enable Debug Logging](#enable-debug-logging)
  - [View Logs](#view-logs)
  - [Using pytest with pdb](#using-pytest-with-pdb)
- [Continuous Integration](#continuous-integration)
- [Contributing Workflow](#contributing-workflow)
- [Troubleshooting](#troubleshooting)
  - [Tests Fail with Import Errors](#tests-fail-with-import-errors)
  - [Home Assistant Doesn't Detect the Integration](#home-assistant-doesnt-detect-the-integration)
  - [Coverage Report Shows Missing Lines](#coverage-report-shows-missing-lines)
  - [Pre-commit Hooks Failing](#pre-commit-hooks-failing)
- [Resources](#resources)
- [Getting Help](#getting-help)

## Prerequisites

- Python 3.13
- Git
- A Home Assistant installation (for manual testing)

## Quick Start

Run the automated setup script:

```bash
./setup-dev.sh
```

This will:
- Install pre-commit hooks
- Install test dependencies
- Run initial linting and tests

Or follow the manual setup steps below.

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

# Install test dependencies (includes pre-commit)
pip install -r requirements_test.txt

# Install runtime dependencies
pip install -r requirements.txt
```

### 4. Install Pre-commit Hooks

Pre-commit hooks automatically check your code before each commit:

```bash
# Install the git hooks (pre-commit is already installed from requirements_test.txt)
pre-commit install
```

Now every commit will automatically:
- Run Ruff linting with auto-fix
- Format code with Ruff
- Remove trailing whitespace
- Validate YAML files
- Run tests on changed files

**Important**: Pre-commit uses the Python environment where it was installed. Always activate your virtual environment before committing:
```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
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
pytest tests/ --cov=custom_components/ha_scheduler --cov-report=term
```

### Run Tests with Detailed Coverage (shows missing lines)

```bash
pytest tests/ --cov=custom_components/ha_scheduler --cov-report=term-missing
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

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit. They will:
- Fix linting issues automatically
- Format code
- Block commits if there are unfixable errors

To skip hooks (not recommended):
```bash
git commit --no-verify
```

### Run Linting with Ruff

```bash
# Check for issues
ruff check custom_components/ha_scheduler/ tests/

# Auto-fix issues
ruff check --fix custom_components/ha_scheduler/ tests/
```

### Run Code Formatting with Ruff

```bash
# Check formatting
ruff format --check custom_components/ha_scheduler/ tests/

# Auto-format code
ruff format custom_components/ha_scheduler/ tests/
```

### Manual Pre-commit Check

Run all pre-commit checks manually:

```bash
# Run on all files
pre-commit run --all-files

# Update pre-commit hooks
pre-commit autoupdate
```

## Running Home Assistant Locally

### Option 1: Local Development Instance (Recommended)

Run a local Home Assistant instance in a separate virtual environment for development and testing.

#### 1. Create a Separate Virtual Environment for Home Assistant

```bash
# Create a new directory for your HA development instance
mkdir -p ~/ha-dev
cd ~/ha-dev

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Home Assistant
pip install homeassistant
```

#### 2. Create Configuration Directory

```bash
# Create config directory
mkdir -p config/custom_components

# Symlink your integration
ln -s /path/to/ha-scheduler/custom_components/ha_scheduler config/custom_components/ha_scheduler
```

#### 3. Start Home Assistant

```bash
# Start Home Assistant (will create default configuration on first run)
hass -c config

# Or run in verbose mode for debugging
hass -c config --debug
```

#### 4. Access Home Assistant

Open your browser and go to `http://localhost:8123`

#### 5. Stop Home Assistant

Press `Ctrl+C` in the terminal where Home Assistant is running.

### Option 2: Using Existing Home Assistant Installation

If you already have Home Assistant installed, you can test your integration there.

#### Method A: Symlink (Recommended for Development)

1. Locate your Home Assistant configuration directory (usually `~/.homeassistant` or `/config`)

2. Create a symlink to your development directory:

```bash
ln -s /path/to/ha-scheduler/custom_components/ha_scheduler ~/.homeassistant/custom_components/ha_scheduler
```

3. Restart Home Assistant

#### Method B: Copy Files

1. Copy the integration to your Home Assistant custom_components directory:

```bash
cp -r custom_components/ha_scheduler ~/.homeassistant/custom_components/
```

2. Restart Home Assistant after each change

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Scheduler"
4. Follow the configuration steps

### Hot Reloading During Development

When developing, you can reload your integration without restarting Home Assistant:

1. Go to **Developer Tools** → **YAML**
2. Click **Reload** next to "Custom Integrations" (if available)
3. Or restart Home Assistant from **Settings** → **System** → **Restart**

Note: Some changes (like manifest.json updates) require a full restart.

## Debugging Tips

### Enable Debug Logging

Add to your Home Assistant `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.ha_scheduler: debug
```

### View Logs

```bash
# Follow logs in real-time
tail -f ~/.homeassistant/home-assistant.log | grep ha_scheduler
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
- **Lint Workflow**: Checks code quality with Ruff (linting and formatting)
- **Validate Workflow**: Validates HACS and Home Assistant compliance
- **CodeQL**: Security analysis

All workflows run on Python 3.13.

Check the Actions tab in GitHub to see results. Pre-commit hooks catch most issues locally before pushing.

## Contributing Workflow

1. **Create a branch** for your feature/fix:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes** with proper tests

3. **Run tests** to ensure everything works:
   ```bash
   pytest tests/ --cov=custom_components/ha_scheduler
   ```

4. **Commit your changes** (pre-commit hooks run automatically):
   ```bash
   git add .
   git commit -m "Add my new feature"
   ```

   If pre-commit hooks fail:
   - Review the error messages
   - Hooks will auto-fix most issues
   - Stage the fixed files: `git add .`
   - Commit again

5. **Push** and create a pull request:
   ```bash
   git push origin feature/my-new-feature
   ```

6. **GitHub Actions** will automatically verify your changes

### Code Style

This project follows Home Assistant's coding standards:

- Python 3.13+
- Type hints required
- Ruff for linting and formatting
- Pytest for testing
- American English for all text
- Test coverage >95%

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
pytest tests/ --cov=custom_components/ha_scheduler --cov-report=term-missing
```

Then add tests to cover those lines.

### Pre-commit Hooks Failing

If pre-commit hooks fail:

1. Review the error messages
2. Most issues are auto-fixed by hooks
3. Stage the fixed files: `git add .`
4. Commit again

For manual fixes:
```bash
# Fix linting issues
ruff check --fix custom_components/ha_scheduler/ tests/

# Format code
ruff format custom_components/ha_scheduler/ tests/

# Run all checks
pre-commit run --all-files
```

## Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Documentation](https://hacs.xyz/)
- [pytest Documentation](https://docs.pytest.org/)
- [Home Assistant Custom Component Testing](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)

## Getting Help

- Open an issue on [GitHub](https://github.com/Smiley73/ha-scheduler/issues)
- Check existing issues for similar problems
- Provide logs and error messages when reporting issues
