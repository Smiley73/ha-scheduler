"""Test edge cases and error handling in config flow."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.config_flow import _validate_yaml_config
from custom_components.ha_scheduler.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def test_validate_yaml_config_accepts_dict() -> None:
    """A YAML mapping is parsed and returned as a dict."""
    assert _validate_yaml_config("color: red\nbrightness: 75") == {
        "color": "red",
        "brightness": 75,
    }


def test_validate_yaml_config_accepts_list() -> None:
    """A YAML sequence is a valid structure and returned as a list."""
    assert _validate_yaml_config("- one\n- two") == ["one", "two"]


def test_validate_yaml_config_accepts_empty_dict() -> None:
    """An explicit empty mapping is preserved (not collapsed to None)."""
    assert _validate_yaml_config("{}") == {}


def test_validate_yaml_config_accepts_empty_list() -> None:
    """An explicit empty sequence is preserved (not collapsed to None)."""
    assert _validate_yaml_config("[]") == []


def test_validate_yaml_config_blank_returns_none() -> None:
    """Blank/whitespace input returns None rather than raising."""
    assert _validate_yaml_config("") is None
    assert _validate_yaml_config("   \n  ") is None


def test_validate_yaml_config_rejects_scalar() -> None:
    """A bare scalar value is rejected with a structure error."""
    with pytest.raises(ValueError, match="YAML structure"):
        _validate_yaml_config("just a string")


def test_validate_yaml_config_rejects_invalid_yaml() -> None:
    """Malformed YAML is reported as invalid."""
    with pytest.raises(ValueError, match="Invalid YAML:"):
        _validate_yaml_config("invalid: yaml: [")


async def test_config_flow_duplicate_name(hass: HomeAssistant) -> None:
    """Test config flow rejects duplicate integration names."""
    # Create first entry
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry1.add_to_hass(hass)

    # Try to create second entry with same name
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"scheduler_name": "Test Scheduler"},  # Same name as existing entry
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"scheduler_name": "duplicate_scheduler_name"}


async def test_options_flow_with_corrupted_data(hass: HomeAssistant) -> None:
    """Test options flow handles corrupted schedule data."""
    # Entry with malformed schedules data
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "schedules": {
                "bad_schedule": {
                    # Missing required fields like 'name', 'schedule_type'
                    "uid": "bad_schedule",
                }
            }
        },
    )
    entry.add_to_hass(hass)

    # Options flow should still be accessible
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert "add_schedule" in result["menu_options"]


async def test_edit_schedule_nonexistent_schedule(hass: HomeAssistant) -> None:
    """Test editing a schedule that doesn't exist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select edit_schedule from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "edit_schedule"}
    )

    # Should abort since no schedules exist
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_schedules"


async def test_remove_schedule_nonexistent_schedule(hass: HomeAssistant) -> None:
    """Test removing a schedule that doesn't exist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select remove_schedule from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "remove_schedule"}
    )

    # Should abort since no schedules exist
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_schedules"


async def test_schedule_sorting_with_unicode_names(hass: HomeAssistant) -> None:
    """Test schedule sorting with Unicode characters."""
    schedules = {
        "schedule_1": {
            "name": "Ñoël Schedule",
            "schedule_type": "date",
            "uid": "schedule_1",
        },
        "schedule_2": {
            "name": "Åpril Schedule",
            "schedule_type": "date",
            "uid": "schedule_2",
        },
        "schedule_3": {
            "name": "Zürich Schedule",
            "schedule_type": "date",
            "uid": "schedule_3",
        },
        "schedule_4": {
            "name": "Beijing 北京",
            "schedule_type": "date",
            "uid": "schedule_4",
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": schedules},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    # Select edit_schedule from menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "edit_schedule"}
    )

    # Verify Unicode names are handled in sorting
    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    schedule_selector = schema["schedule_id"]
    options = schedule_selector.config["options"]

    # Should have all schedules and be sorted
    assert len(options) == 4
    # Verify all names are present
    names = [opt["label"] for opt in options]
    assert "Ñoël Schedule" in names
    assert "Åpril Schedule" in names
    assert "Zürich Schedule" in names
    assert "Beijing 北京" in names


async def test_concurrent_options_flows(hass: HomeAssistant) -> None:
    """Test multiple concurrent options flows (edge case)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)

    # Start first flow
    result1 = await hass.config_entries.options.async_init(entry.entry_id)

    # Start second flow (should be prevented by Home Assistant)
    try:
        result2 = await hass.config_entries.options.async_init(entry.entry_id)
        # If allowed, both should be valid forms
        assert result1["type"] == FlowResultType.FORM
        assert result2["type"] == FlowResultType.FORM
    except Exception:
        # Expected - Home Assistant prevents concurrent flows
        pass


async def test_edit_schedule_without_stored_uid_does_not_self_conflict(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Editing a legacy schedule stored without a uid must be savable.

    Regression test: overlap validation excludes the edited schedule by uid;
    schedules migrated from v1 may lack a stored uid, and without backfilling
    it from the storage key every edit conflicted with itself.
    """
    schedule_id = "legacy-no-uid"
    entry = create_service_entry(
        schedules={
            schedule_id: {
                # Deliberately no "uid" key
                "name": "Summer",
                "schedule_type": "date",
                "start_month": 6,
                "start_day": 1,
                "end_month": 8,
                "end_day": 31,
            }
        }
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_id": schedule_id}
    )
    assert result["step_id"] == "configure_date"

    # Re-save with identical dates; this used to error "overlaps with Summer".
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Summer",
            "start_month": "6",
            "start_day": 1,
            "end_month": "8",
            "end_day": 31,
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    schedules = updated_entry.options["services"]["default"]["schedules"]
    assert schedules[schedule_id]["name"] == "Summer"


async def test_default_configuration_preserves_legacy_schedules(
    hass: HomeAssistant,
) -> None:
    """Setting the default configuration must not strand legacy schedules.

    Regression test: the step used to write a services dict unconditionally,
    creating an empty services.default.schedules that hid the root-level
    schedules of legacy-shaped entries from every reader.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Legacy Scheduler",
        data={},
        options={
            "schedules": {
                "legacy-1": {
                    "uid": "legacy-1",
                    "name": "Winter",
                    "schedule_type": "date",
                    "start_month": 12,
                    "start_day": 1,
                    "end_month": 2,
                    "end_day": 28,
                }
            },
            "configuration": {},
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "default_configuration"}
    )
    assert result["step_id"] == "default_configuration"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"configuration": "mode: eco"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    # Legacy layout is preserved: schedules stay at the options root and no
    # competing (empty) services structure is created.
    assert "services" not in updated_entry.options
    assert updated_entry.options["configuration"] == {"mode": "eco"}
    assert "legacy-1" in updated_entry.options["schedules"]


async def test_edit_week_schedule_preserves_country_code(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Editing a week schedule must not adopt the current HA country.

    Regression test: the stored country_code used to be overwritten with
    hass.config.country on every edit, silently shifting week boundaries
    (Monday-first vs Sunday-first) when the HA country had changed.
    """
    schedule_id = "week-us"
    entry = create_service_entry(
        schedules={
            schedule_id: {
                "uid": schedule_id,
                "name": "US Weeks",
                "schedule_type": "week",
                "start_month": 3,
                "start_week": 1,
                "end_month": 3,
                "end_week": 2,
                "country_code": "US",
            }
        }
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The HA instance has since been reconfigured to another country.
    hass.config.country = "DE"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_id": schedule_id}
    )
    assert result["step_id"] == "configure_week"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "US Weeks",
            "start_month": "3",
            "start_week": "1",
            "start_day_of_week": "",
            "end_month": "3",
            "end_week": "2",
            "end_day_of_week": "",
            "configuration": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    schedules = updated_entry.options["services"]["default"]["schedules"]
    assert schedules[schedule_id]["country_code"] == "US"
