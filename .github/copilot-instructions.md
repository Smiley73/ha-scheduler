# Contributor & AI Agent Guide — ha-scheduler

This repository is a **Home Assistant custom integration** (HACS category:
integration, domain `ha_scheduler`), not Home Assistant core. It provides
calendar entities whose all-day events are generated from schedule rules.

## What it does

Users define schedules per config entry ("scheduler"); each scheduler exposes
one calendar entity. Four schedule types, all stored in
`entry.options["services"]["default"]["schedules"]`:

- `date` — fixed month/day range, may wrap the year (Dec 15 → Jan 15)
- `week` — nth calendar week of a month, optionally bounded by weekdays;
  "first week" comes in `partial` and `full` variants; week starts depend on
  the schedule's `country_code` (Monday-first vs Sunday-first via Babel)
- `nth-day` — nth weekday of a month (occurrence 0-4, 4 = last) with
  `start_offset`/`end_offset` days
- `holiday` — resolved each year from the `holidays` library by
  country/category/name

## Layout

- `custom_components/ha_scheduler/`
  - `config_flow.py` — config + options flows (add/edit/remove/import
    holidays/default configuration)
  - `schedule_generator.py` — pure date math; `generate_schedule_dates()` is
    the single entry point; overlap validation uses a 400-year Gregorian
    cycle (lru_cached)
  - `holiday_importer.py` — `holidays`/Babel access, pattern analysis for
    imports, cache priming helpers
  - `calendar.py` — the `SchedulerCalendar` entity
  - `migrations.py` — config entry v1 (helper) → v2 (service) migration
- `tests/` — pytest with `pytest-homeassistant-custom-component` (real
  `hass` fixture); shared fixtures in `tests/conftest.py`
  (`create_service_entry` builds a v2 entry)

## Dev setup and commands

```bash
python3 -m venv .venv && source .venv/bin/activate
./setup-dev.sh                 # installs requirements_test.txt + pre-commit
pytest tests/ -q               # full suite (fast, ~2s)
ruff check custom_components/ tests/ && ruff format --check custom_components/ tests/
```

CI runs tests on Python 3.14 with a 95% coverage gate, ruff over
`custom_components/` and `tests/`, hassfest + HACS validation, and CodeQL.
Runtime dependencies are unpinned floors; a weekly scheduled test run catches
upstream `holidays`/`babel`/`homeassistant` changes. Lint tooling (`ruff`,
`mypy`) is bounded to a minor series instead, so a new rule cannot turn CI red
without a commit; pre-commit runs ruff from that same install.

## Conventions and gotchas

- **Event-loop discipline**: `holidays` and Babel do blocking I/O on first
  use. Never call them directly from async code — use
  `async_prime_holiday_cache()` / `hass.async_add_executor_job`. The
  calendar entity primes caches at setup, on options updates, and in a
  daily midnight refresh.
- **All-day events**: `CalendarEvent.end` is exclusive → stored end date
  + 1 day. `async_get_events` bounds are half-open per the HA calendar
  contract.
- **Entity naming**: `_attr_has_entity_name = True` with a `None` name for
  the default service so the entity takes the device name. Never define a
  member named `_async_update_listener` on the entity —
  `CalendarEntity` owns that name (HA 2026.6+) and shadowing it breaks
  dashboards; a resilience test guards this.
- **Schedule dicts**: every schedule carries a `uid` (backfilled from its
  storage key for legacy entries). Overlap checks exclude the edited
  schedule by uid.
- **Options writes**: use `_save_schedule`/`_remove_schedule` in the options
  flow (merge-on-write against a fresh read); do not write a stale snapshot.
- **Translations**: `strings.json` and `translations/en.json` must stay
  byte-for-byte identical. Selector option labels live under `selector` and
  are keyed by option *values*.
- **Legacy layout**: entries may store `schedules`/`configuration` at the
  options root (pre-services). Every reader/writer must handle both shapes
  or migrate deliberately — no half-support.
- **Versioning**: bump `manifest.json` version for every user-visible change;
  keep `SPEC.md` in sync. Config entry migrations live in `migrations.py`
  with `CURRENT_VERSION`/`CURRENT_MINOR_VERSION`.
- **Quality scale**: manifest claims `gold`; `quality_scale.yaml` tracks
  the honest per-rule status. Do not raise the claim without completing the
  rules.
