# Development Guide

Setup, tests and CI for contributors. For installing and using the integration,
see the [README](README.md); agents also read [AGENTS.md](AGENTS.md).

## Setup

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
uv fetches the Python version pinned in `.python-version` (3.14) itself.

```bash
git clone https://github.com/Smiley73/ha-scheduler.git
cd ha-scheduler
uv sync --locked
./setup-dev.sh
```

`uv sync --locked` creates `.venv` with exactly the versions in `uv.lock`. The
script syncs the same way, installs the pre-commit hooks (from the main
checkout only) and runs ruff and the tests once. The hooks are shared by every
worktree, so a new worktree needs only `uv sync --locked`.

## Tests and lint

`uv run` re-syncs `.venv` before running, so no activation is needed.

```bash
uv run pytest tests/ -q          # add a path or ::test_name to narrow it
uv run pytest tests/ --cov=custom_components/ha_scheduler --cov-report=term-missing --cov-fail-under=95
uv run ruff check custom_components/ tests/ && uv run ruff format --check custom_components/ tests/
uv run mypy custom_components/ha_scheduler/
uv run pre-commit run --all-files
```

The coverage command mirrors the CI gate. Use `uv run pytest tests/ -s` with
`breakpoint()` to debug a test.

## Pre-commit

Every commit runs the hooks in `.pre-commit-config.yaml`: ruff check (with
`--fix`), ruff format, mypy, the test suite, and the whitespace, end-of-file,
YAML, large-file and merge-conflict checks. Hooks fix what they can; stage the
fixes and commit again. `git commit --no-verify` skips them, but CI will not.

The ruff, mypy and pytest hooks run through `uv run --locked` against
`uv.lock` from any checkout or worktree, with no venv to activate. They fail
if `pyproject.toml` and `uv.lock` disagree.

`pre-commit autoupdate` does not manage ruff, mypy or pytest; their versions
come from `uv.lock`. To change a dependency, edit `pyproject.toml` (or use
`uv add` / `uv lock --upgrade-package <name>`), run `uv lock`, and commit both
files. Dependabot opens PRs that refresh `uv.lock`.

## Running Home Assistant locally

Use a separate venv so Home Assistant's dependencies stay out of the test venv,
and symlink the integration into its config directory:

```bash
mkdir -p ~/ha-dev/config/custom_components && cd ~/ha-dev
uv venv && source .venv/bin/activate
uv pip install homeassistant
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

GitHub Actions, all on Python 3.14 and installing with `uv sync --locked`. They
run on push, pull request and manual dispatch, with no scheduled run:

- **Test**: pytest with the 95% coverage gate
- **Lint**: ruff, mypy and the repo hygiene pre-commit hooks
- **Validate**: HACS and hassfest
- **CodeQL**: security analysis

## Code style

- Home Assistant's coding standards, formatted and linted by ruff
- Type hints required
- American English for all text
- Test coverage at or above the 95% CI gate
