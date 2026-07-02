"""Tests for the config entry migration system.

Covers the failure path of the v1->v2 migration (helper raises, migration
aborts and logs) and the 0.5.2 minor-only version bump (same major version,
stale minor gets bumped without touching data/options).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.const import DOMAIN
from custom_components.ha_scheduler.migrations import async_migrate_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_v1_to_v2_migration_failure_logs_and_returns_false(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failure while migrating v1 data aborts the migration cleanly.

    If `async_update_entry` blows up inside `async_migrate_v1_to_v2`, the
    helper must catch it, log an exception, and return False (migrations.py
    line 103-105). `async_migrate_entry` must then propagate that False
    (line 33) instead of continuing to bump the version.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Legacy Scheduler",
        data={},
        options={
            "schedules": {
                "old_schedule": {
                    "name": "Old Schedule",
                    "schedule_type": "date",
                    "start_month": 6,
                    "start_day": 1,
                    "end_month": 8,
                    "end_day": 31,
                }
            },
            "configuration": {},
        },
        version=1,
    )
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_update_entry",
        side_effect=RuntimeError("boom"),
    ):
        result = await async_migrate_entry(hass, entry)

    assert result is False

    assert any(
        record.levelname == "ERROR"
        and "Failed to migrate config entry" in record.message
        and record.exc_info is not None
        for record in caplog.records
    )

    # Migration bailed out before ever touching the version numbers.
    assert entry.version == 1
    assert entry.minor_version == 1


async def test_minor_only_bump_updates_minor_version_only(
    hass: HomeAssistant,
) -> None:
    """A same-major, stale-minor entry (v0.5.2 behavior) just bumps minor.

    version == CURRENT_VERSION (2) but minor_version (0) is behind
    CURRENT_MINOR_VERSION (1): no structural migration runs, but
    async_update_entry must still be called to persist the new minor
    version, otherwise core re-offers the entry for migration on every
    restart (migrations.py line 41).
    """
    original_data = {"scheduler_name": "Current Scheduler"}
    original_options = {
        "services": {
            "default": {
                "name": "Current Scheduler",
                "schedules": {},
                "configuration": {},
            }
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Current Scheduler",
        data=original_data,
        options=original_options,
        version=2,
        minor_version=0,
    )
    entry.add_to_hass(hass)

    mock_update_entry = MagicMock(return_value=True)
    with patch.object(hass.config_entries, "async_update_entry", mock_update_entry):
        result = await async_migrate_entry(hass, entry)

    assert result is True

    mock_update_entry.assert_called_once_with(entry, version=2, minor_version=1)

    # Only version numbers were passed - data/options were left untouched.
    _, kwargs = mock_update_entry.call_args
    assert "data" not in kwargs
    assert "options" not in kwargs
    assert entry.data == original_data
    assert entry.options == original_options
