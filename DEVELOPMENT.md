# Development Guide

Setup, tests and CI for contributors. For installing and using the integration,
see the [README](README.md); agents also read [AGENTS.md](AGENTS.md).

## Setup

Requires Python 3.14 (what CI runs) and Git.

```bash
git clone https://github.com/Smiley73/ha-scheduler.git
cd ha-scheduler
python3 -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
./setup-dev.sh
```

The script installs `requirements_test.txt`, installs the pre-commit hooks and
runs ruff and the tests once. To do it by hand:

```bash
pip install --upgrade -r requirements_test.txt
pip install -r requirements.txt  # pytest-homeassistant-custom-component pins homeassistant
pre-commit install
```

## Tests and lint

```bash
pytest tests/ -q                 # add a path or ::test_name to narrow it
pytest tests/ --cov=custom_components/ha_scheduler --cov-report=term-missing --cov-fail-under=95
ruff check custom_components/ tests/ && ruff format --check custom_components/ tests/
mypy custom_components/ha_scheduler/
pre-commit run --all-files
```

The coverage command mirrors the CI gate. Use `pytest tests/ -s` with
`breakpoint()` to debug a test.

## Pre-commit

Every commit runs the hooks in `.pre-commit-config.yaml`: ruff check (with
`--fix`), ruff format, mypy, the test suite, and the whitespace, end-of-file,
YAML, large-file and merge-conflict checks. Hooks fix what they can; stage the
fixes and commit again. `git commit --no-verify` skips them, but CI will not.

Pre-commit runs in the environment where it was installed, so activate the
venv before committing.

`pre-commit autoupdate` does not manage ruff, mypy or pytest: they run as local
`system` hooks against the versions from `requirements_test.txt`. Bump them
there (dependabot opens those PRs) and re-run `pip install -r
requirements_test.txt`.

## Running Home Assistant locally

Use a separate venv so Home Assistant's dependencies stay out of the test venv,
and symlink the integration into its config directory:

```bash
mkdir -p ~/ha-dev/config/custom_components && cd ~/ha-dev
python3 -m venv .venv && source .venv/bin/activate
pip install homeassistant
ln -s /path/to/ha-scheduler/custom_components/ha_scheduler config/custom_components/ha_scheduler
hass -c config --debug
```

Open `http://localhost:8123`, then add the integration as described in the
[README](README.md#initial-setup). Restart Home Assistant after
changing the integration. For an existing installation, symlink
`custom_components/ha_scheduler` into its `custom_components` directory the
same way.

Debug logging is described under
[Troubleshooting](README.md#-troubleshooting) in the README.

## Continuous integration

GitHub Actions, all on Python 3.14:

- **Test**: pytest with the 95% coverage gate
- **Lint**: ruff, mypy and the repo hygiene pre-commit hooks
- **Validate**: HACS and hassfest
- **CodeQL**: security analysis

## Code style

- Home Assistant's coding standards, formatted and linted by ruff
- Type hints required
- American English for all text
- Test coverage at or above the 95% CI gate
