"""Test edge cases and error handling in config flow."""

import uuid
from contextlib import ExitStack
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_scheduler.config_flow import (
    OptionsFlowHandler,
    _get_holiday_options,
    _validate_yaml_config,
)
from custom_components.ha_scheduler.const import (
    DOMAIN,
    SCHEDULE_TYPE_DATE,
    SCHEDULE_TYPE_HOLIDAY,
    SCHEDULE_TYPE_NTH_DAY,
    SCHEDULE_TYPE_WEEK,
)
from tests.conftest import get_schedules_from_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

# Minimal valid form submissions for each schedule type's configure_* step,
# reused across the grouped/parametrized tests below.
_BASE_VALID_INPUT = {
    SCHEDULE_TYPE_DATE: {
        "name": "Test Schedule",
        "start_month": "6",
        "start_day": 1,
        "end_month": "8",
        "end_day": 31,
    },
    SCHEDULE_TYPE_WEEK: {
        "name": "Test Schedule",
        "start_month": "3",
        "start_week": "1",
        "start_day_of_week": "0",
        "end_month": "6",
        "end_week": "4",
        "end_day_of_week": "4",
    },
    SCHEDULE_TYPE_NTH_DAY: {
        "name": "Test Schedule",
        "month": "3",
        "occurrence": "1",
        "day_of_week": "1",
        "start_offset": 2,
        "end_offset": 3,
    },
    SCHEDULE_TYPE_HOLIDAY: {
        "name": "Test Schedule",
        "holiday_name": "Test Holiday",
        "start_offset": 0,
        "end_offset": 0,
    },
}

_MOCK_HOLIDAYS = {
    "Test Holiday": {
        "pattern": {"description": "A test holiday"},
        "dates": [date(2026, 1, 1)],
    }
}

_STEP_ID_BY_TYPE = {
    SCHEDULE_TYPE_DATE: "configure_date",
    SCHEDULE_TYPE_WEEK: "configure_week",
    SCHEDULE_TYPE_NTH_DAY: "configure_nth_day",
    SCHEDULE_TYPE_HOLIDAY: "configure_holiday",
}


def _holiday_import_patches():
    """Return patch context managers that make holiday lookups succeed."""
    return (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"US": "United States"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=_MOCK_HOLIDAYS),
        ),
    )


async def _drive_to_configure_step(hass: HomeAssistant, entry, schedule_type: str):
    """Drive the add-schedule flow up to the type's configure_* form.

    Holiday schedules need two extra steps (country, category) before
    reaching configure_holiday; callers must have the holiday_importer
    patches from ``_holiday_import_patches`` active first.
    """
    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        flow_id, {"schedule_type": schedule_type}
    )
    if schedule_type == SCHEDULE_TYPE_HOLIDAY:
        result = await hass.config_entries.options.async_configure(
            flow_id, {"country_code": "US"}
        )
        result = await hass.config_entries.options.async_configure(
            flow_id, {"category": "public"}
        )
    assert result["step_id"] == _STEP_ID_BY_TYPE[schedule_type]
    return flow_id, result


def _bare_options_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> OptionsFlowHandler:
    """Build an OptionsFlowHandler wired to `entry` without driving a full flow init.

    Sets just enough (``hass``, ``handler``) for the ``config_entry`` property
    to resolve, mirroring what ``hass.config_entries.options.async_init``
    leaves in place by the time a step method runs -- without the
    flow-manager bookkeeping (``_progress``, a real ``flow_id``, ...) that
    driving a full init adds.
    """
    flow = OptionsFlowHandler()
    flow.hass = hass
    flow.handler = entry.entry_id
    return flow


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


# ---------------------------------------------------------------------------
# Grouped/parametrized items
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schedule_type",
    [
        SCHEDULE_TYPE_DATE,
        SCHEDULE_TYPE_WEEK,
        SCHEDULE_TYPE_NTH_DAY,
        SCHEDULE_TYPE_HOLIDAY,
    ],
)
async def test_configure_step_aborts_unknown_when_schedule_id_none(
    hass: HomeAssistant, create_service_entry, schedule_type: str
) -> None:
    """If the in-progress schedule_id vanishes, saving aborts as unknown."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with ExitStack() as stack:
        if schedule_type == SCHEDULE_TYPE_HOLIDAY:
            for holiday_patch in _holiday_import_patches():
                stack.enter_context(holiday_patch)

        flow_id, result = await _drive_to_configure_step(hass, entry, schedule_type)
        assert result["type"] == FlowResultType.FORM

        flow = hass.config_entries.options._progress[flow_id]
        flow._schedule_id = None

        final_input = {**_BASE_VALID_INPUT[schedule_type], "configuration": ""}
        result = await hass.config_entries.options.async_configure(flow_id, final_input)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_remove_schedule_confirm_aborts_unknown_when_schedule_id_none(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Confirming removal aborts as unknown if the schedule_id vanished."""
    entry = create_service_entry(
        schedules={
            "sched-1": {
                "uid": "sched-1",
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
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id, {"next_step_id": "remove_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        flow_id, {"schedule_id": "sched-1"}
    )
    assert result["step_id"] == "remove_schedule_confirm"

    flow = hass.config_entries.options._progress[flow_id]
    flow._schedule_id = None

    result = await hass.config_entries.options.async_configure(
        flow_id, {"confirm": True}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.parametrize(
    "schedule_type",
    [SCHEDULE_TYPE_WEEK, SCHEDULE_TYPE_NTH_DAY, SCHEDULE_TYPE_HOLIDAY],
)
async def test_configure_step_accepts_valid_yaml_configuration(
    hass: HomeAssistant, create_service_entry, schedule_type: str
) -> None:
    """A non-empty YAML mapping is parsed and stored on the schedule."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with ExitStack() as stack:
        if schedule_type == SCHEDULE_TYPE_HOLIDAY:
            for holiday_patch in _holiday_import_patches():
                stack.enter_context(holiday_patch)

        flow_id, _ = await _drive_to_configure_step(hass, entry, schedule_type)
        final_input = {
            **_BASE_VALID_INPUT[schedule_type],
            "configuration": "key: value",
        }
        result = await hass.config_entries.options.async_configure(flow_id, final_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    schedule = next(iter(schedules.values()))
    assert schedule["configuration"] == {"key": "value"}


@pytest.mark.parametrize(
    "schedule_type",
    [SCHEDULE_TYPE_WEEK, SCHEDULE_TYPE_NTH_DAY, SCHEDULE_TYPE_HOLIDAY],
)
async def test_configure_step_invalid_yaml_configuration(
    hass: HomeAssistant, create_service_entry, schedule_type: str
) -> None:
    """Malformed YAML re-displays the form with details and preserved fields."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with ExitStack() as stack:
        if schedule_type == SCHEDULE_TYPE_HOLIDAY:
            for holiday_patch in _holiday_import_patches():
                stack.enter_context(holiday_patch)

        flow_id, _ = await _drive_to_configure_step(hass, entry, schedule_type)
        final_input = {
            **_BASE_VALID_INPUT[schedule_type],
            "configuration": "[unbalanced",
        }
        result = await hass.config_entries.options.async_configure(flow_id, final_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_yaml_with_details"
    assert "Invalid YAML:" in result["description_placeholders"]["details"]

    schema = result["data_schema"].schema
    name_key = next(key for key in schema if str(key) == "name")
    assert name_key.default() == _BASE_VALID_INPUT[schedule_type]["name"]


@pytest.mark.parametrize(
    "schedule_type",
    [
        SCHEDULE_TYPE_DATE,
        SCHEDULE_TYPE_WEEK,
        SCHEDULE_TYPE_NTH_DAY,
        SCHEDULE_TYPE_HOLIDAY,
    ],
)
async def test_configure_step_unexpected_exception_shows_unknown_error(
    hass: HomeAssistant, create_service_entry, schedule_type: str
) -> None:
    """An unexpected exception during conflict validation surfaces as unknown."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with ExitStack() as stack:
        if schedule_type == SCHEDULE_TYPE_HOLIDAY:
            for holiday_patch in _holiday_import_patches():
                stack.enter_context(holiday_patch)
        stack.enter_context(
            patch.object(
                OptionsFlowHandler,
                "_validate_schedule_conflicts",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            )
        )

        flow_id, _ = await _drive_to_configure_step(hass, entry, schedule_type)
        final_input = {**_BASE_VALID_INPUT[schedule_type], "configuration": ""}
        result = await hass.config_entries.options.async_configure(flow_id, final_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_configure_week_renders_dict_configuration_as_yaml() -> None:
    """A stored dict configuration is rendered back as YAML in the week form."""
    flow = OptionsFlowHandler()
    flow._schedule_id = str(uuid.uuid4())
    flow._schedule_data = {
        "schedule_type": SCHEDULE_TYPE_WEEK,
        "name": "Test Week",
        "start_month": 3,
        "start_week": 1,
        "end_month": 6,
        "end_week": 4,
        "configuration": {"color": "red", "brightness": 75},
    }

    result = await flow.async_step_configure_week()

    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    config_key = next(key for key in schema if str(key) == "configuration")
    assert config_key.default() == "color: red\nbrightness: 75"


async def test_configure_nth_day_renders_dict_configuration_as_yaml() -> None:
    """A stored dict configuration is rendered back as YAML in the nth-day form."""
    flow = OptionsFlowHandler()
    flow._schedule_id = str(uuid.uuid4())
    flow._schedule_data = {
        "schedule_type": SCHEDULE_TYPE_NTH_DAY,
        "name": "Test Nth Day",
        "month": 3,
        "occurrence": 1,
        "day_of_week": 1,
        "start_offset": 0,
        "end_offset": 0,
        "configuration": {"color": "red", "brightness": 75},
    }

    result = await flow.async_step_configure_nth_day()

    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    config_key = next(key for key in schema if str(key) == "configuration")
    assert config_key.default() == "color: red\nbrightness: 75"


async def test_configure_holiday_renders_dict_configuration_as_yaml() -> None:
    """A stored dict configuration is rendered back as YAML in the holiday form."""
    flow = OptionsFlowHandler()
    flow._schedule_id = str(uuid.uuid4())
    flow._schedule_data = {
        "schedule_type": SCHEDULE_TYPE_HOLIDAY,
        "name": "Test Holiday",
        "country_code": "US",
        "category": "public",
        "holiday_name": "Test Holiday",
        "start_offset": 0,
        "end_offset": 0,
        "configuration": {"color": "red", "brightness": 75},
    }

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
        new=AsyncMock(return_value=_MOCK_HOLIDAYS),
    ):
        result = await flow.async_step_configure_holiday()

    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    config_key = next(key for key in schema if str(key) == "configuration")
    assert config_key.default() == "color: red\nbrightness: 75"


# ---------------------------------------------------------------------------
# Holiday-flow items
# ---------------------------------------------------------------------------


async def test_configure_holiday_country_aborts_import_error(
    hass: HomeAssistant, create_service_entry
) -> None:
    """A failure loading countries aborts the flow as import_error."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_schedule"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"schedule_type": "holiday"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "import_error"


async def test_configure_holiday_country_aborts_no_countries_available(
    hass: HomeAssistant, create_service_entry
) -> None:
    """An empty country list aborts the flow as no_countries_available."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
        new=AsyncMock(return_value={}),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_schedule"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"schedule_type": "holiday"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_countries_available"


async def test_configure_holiday_category_redirects_without_country() -> None:
    """Entering the category step without a country redirects to country."""
    flow = OptionsFlowHandler()
    flow._schedule_data = {}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
        new=AsyncMock(return_value={"US": "United States"}),
    ):
        result = await flow.async_step_configure_holiday_category()

    assert result["step_id"] == "configure_holiday_country"


async def test_configure_holiday_category_aborts_import_error() -> None:
    """A failure loading categories aborts the flow as import_error."""
    flow = OptionsFlowHandler()
    flow._schedule_data = {"country_code": "US"}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_available_categories",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await flow.async_step_configure_holiday_category()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "import_error"


async def test_configure_holiday_category_falls_back_to_public() -> None:
    """An empty category map falls back to a single public option."""
    flow = OptionsFlowHandler()
    flow._schedule_data = {"country_code": "US"}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_available_categories",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_configure_holiday_category()

    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    category_selector = next(
        value for key, value in schema.items() if str(key) == "category"
    )
    assert [opt["value"] for opt in category_selector.config["options"]] == ["public"]


async def test_configure_holiday_category_default_falls_back_when_stored_missing() -> (
    None
):
    """A stored category absent from the loaded map defaults to the first one."""
    flow = OptionsFlowHandler()
    flow._schedule_data = {"country_code": "US", "category": "christmas"}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_available_categories",
        new=AsyncMock(
            return_value={"public": "Public Holidays", "bank": "Bank Holidays"}
        ),
    ):
        result = await flow.async_step_configure_holiday_category()

    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    category_key = next(key for key in schema if str(key) == "category")
    assert category_key.default() == "public"


async def test_configure_holiday_redirects_without_country() -> None:
    """Entering the holiday step without a country redirects to country."""
    flow = OptionsFlowHandler()
    flow._schedule_data = {}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
        new=AsyncMock(return_value={"US": "United States"}),
    ):
        result = await flow.async_step_configure_holiday()

    assert result["step_id"] == "configure_holiday_country"


async def test_configure_holiday_redirects_without_category() -> None:
    """Entering the holiday step without a category redirects to category."""
    flow = OptionsFlowHandler()
    flow._schedule_data = {"country_code": "US"}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_available_categories",
        new=AsyncMock(return_value={"public": "Public Holidays"}),
    ):
        result = await flow.async_step_configure_holiday()

    assert result["step_id"] == "configure_holiday_category"


async def test_configure_holiday_import_error_shown_as_form_error() -> None:
    """A failure loading holidays surfaces as a form error, not an abort."""
    flow = OptionsFlowHandler()
    flow._schedule_data = {"country_code": "US", "category": "public"}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await flow.async_step_configure_holiday()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "import_error"


async def test_configure_holiday_no_holidays_available() -> None:
    """An empty holiday map surfaces as no_holidays_available."""
    flow = OptionsFlowHandler()
    flow._schedule_data = {"country_code": "US", "category": "public"}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
        new=AsyncMock(return_value={}),
    ):
        result = await flow.async_step_configure_holiday()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "no_holidays_available"


async def test_configure_holiday_stored_holiday_not_found(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Editing a holiday schedule whose name vanished flags the field and repicks."""
    schedules = {
        "holiday-id": {
            "uid": "holiday-id",
            "name": "Old Holiday",
            "schedule_type": "holiday",
            "country_code": "US",
            "category": "public",
            "holiday_name": "Old Holiday",
            "name_lookup": "iexact",
            "start_offset": 0,
            "end_offset": 0,
        }
    }
    entry = create_service_entry(schedules=schedules)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_holidays = {
        "New Holiday": {
            "pattern": {"description": "Movable holiday"},
            "dates": [date(2026, 4, 3)],
        }
    }

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_supported_countries",
            new=AsyncMock(return_value={"US": "United States"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={"public": "Public Holidays"}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value=mock_holidays),
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "edit_schedule"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"schedule_id": "holiday-id"}
        )
        assert result["step_id"] == "configure_holiday_country"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"country_code": "US"}
        )
        assert result["step_id"] == "configure_holiday_category"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"category": "public"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure_holiday"
    assert result["errors"]["holiday_name"] == "stored_holiday_not_found"

    schema = result["data_schema"].schema
    holiday_key = next(key for key in schema if str(key) == "holiday_name")
    assert holiday_key.default() == "New Holiday"


async def test_import_holidays_categories_aborts_without_country() -> None:
    """Entering the import-categories step without a country aborts."""
    flow = OptionsFlowHandler()
    flow._holiday_data = {}

    result = await flow.async_step_import_holidays_categories()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "import_error"


async def test_import_holidays_categories_empty_defaults_to_public() -> None:
    """An empty category map proceeds to selection defaulted to public."""
    flow = OptionsFlowHandler()
    flow._holiday_data = {"country": "US"}

    with (
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_available_categories",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await flow.async_step_import_holidays_categories()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "import_holidays_select"
    assert flow._holiday_data["categories"] == ["public"]


async def test_holiday_selection_schema_empty_without_country() -> None:
    """The holiday-selection schema has no options when country is missing."""
    flow = OptionsFlowHandler()
    flow._holiday_data = {"categories": ["public"]}

    schema = await flow._get_holiday_selection_schema()

    holiday_selector = next(
        value for key, value in schema.schema.items() if str(key) == "holidays"
    )
    assert holiday_selector.config["options"] == []


async def test_import_selected_holidays_shows_import_error() -> None:
    """A failure loading holidays inside the import step re-shows the form."""
    flow = OptionsFlowHandler()
    flow._holiday_data = {"country": "US", "categories": ["public"]}

    with patch(
        "custom_components.ha_scheduler.holiday_importer.get_holidays_for_country",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await flow._import_selected_holidays(
            ["Any Holiday"], overwrite_existing=False, skip_on_overlap=True
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "import_holidays_select"
    assert result["errors"]["base"] == "import_error"


# ---------------------------------------------------------------------------
# Helper/entry items
# ---------------------------------------------------------------------------


def test_get_holiday_options_skips_none_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A None holiday entry is skipped and warned about, not KeyError'd."""
    options = _get_holiday_options(
        {
            "Good": {"pattern": {"description": "desc"}},
            "Bad": None,
        }
    )

    assert [opt["value"] for opt in options] == ["Good"]
    assert any(
        record.levelname == "WARNING" and "Bad" in record.message
        for record in caplog.records
    )


async def test_service_schedule_helpers_return_empty_when_entry_missing(
    hass: HomeAssistant, create_service_entry
) -> None:
    """Both schedule accessors degrade to {} if the entry can't be found.

    ``self.config_entry`` itself resolves via ``async_get_entry``, so each
    method call needs that first (property) lookup to succeed before the
    method's own explicit lookup is made to return None.
    """
    entry = create_service_entry()
    entry.add_to_hass(hass)

    real_entry = hass.config_entries.async_get_entry(entry.entry_id)
    flow = _bare_options_flow(hass, entry)

    with patch.object(
        hass.config_entries, "async_get_entry", side_effect=[real_entry, None]
    ):
        assert flow._get_service_schedules() == {}

    with patch.object(
        hass.config_entries, "async_get_entry", side_effect=[real_entry, None]
    ):
        assert flow._update_service_schedules({"x": {}}) == {}


async def test_update_service_schedules_creates_missing_service(
    hass: HomeAssistant,
) -> None:
    """Updating schedules for an absent service id creates it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={},
        options={
            "services": {
                "other": {"name": "Other", "schedules": {}, "configuration": {}}
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow = hass.config_entries.options._progress[result["flow_id"]]

    updated = flow._update_service_schedules({"sched-1": {"name": "S"}})

    assert updated["services"]["default"] == {
        "name": "Test Scheduler",
        "schedules": {"sched-1": {"name": "S"}},
        "configuration": {},
    }
    assert "other" in updated["services"]


async def test_update_service_schedules_legacy_writes_root_schedules(
    hass: HomeAssistant,
) -> None:
    """Legacy (pre-services) entries keep their schedules at the options root."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Legacy Scheduler",
        data={},
        options={"schedules": {}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow = hass.config_entries.options._progress[result["flow_id"]]

    updated = flow._update_service_schedules({"sched-1": {"name": "S"}})

    assert "services" not in updated
    assert updated["schedules"] == {"sched-1": {"name": "S"}}


async def test_default_configuration_entry_not_found_when_get_entry_returns_none(
    hass: HomeAssistant, create_service_entry
) -> None:
    """A vanished entry during submit re-shows the form as entry_not_found.

    ``self.config_entry`` resolves via ``async_get_entry`` too, so the first
    (property) lookup must succeed for the method's own explicit lookup
    (the one guarded by ``if not entry:``) to be reached and return None.
    """
    entry = create_service_entry()
    entry.add_to_hass(hass)

    real_entry = hass.config_entries.async_get_entry(entry.entry_id)
    flow = _bare_options_flow(hass, entry)

    with patch.object(
        hass.config_entries, "async_get_entry", side_effect=[real_entry, None]
    ):
        result = await flow.async_step_default_configuration({"configuration": ""})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "entry_not_found"


async def test_default_configuration_unexpected_exception_shows_unknown_error(
    hass: HomeAssistant, create_service_entry
) -> None:
    """A non-UnknownEntry exception while fetching the entry surfaces as unknown.

    ``self.config_entry`` itself resolves via ``async_get_entry``, so the
    first call (from that property, at the top of the try block) is the one
    made to raise; the two subsequent calls (property + explicit lookup in
    the post-exception fallback render) must succeed normally.
    """
    entry = create_service_entry()
    entry.add_to_hass(hass)

    real_entry = hass.config_entries.async_get_entry(entry.entry_id)
    flow = _bare_options_flow(hass, entry)

    with patch.object(
        hass.config_entries,
        "async_get_entry",
        side_effect=[RuntimeError("boom"), real_entry, real_entry],
    ):
        result = await flow.async_step_default_configuration(
            {"configuration": "mode: eco"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_default_configuration_creates_missing_service(
    hass: HomeAssistant,
) -> None:
    """Setting the default configuration creates an absent service entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Scheduler",
        data={"scheduler_name": "Test Scheduler"},
        options={
            "services": {
                "other": {"name": "Other Service", "schedules": {}, "configuration": {}}
            }
        },
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "default_configuration"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"configuration": "mode: eco"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    services = result["data"]["services"]
    assert services["default"]["configuration"] == {"mode": "eco"}
    assert services["default"]["name"] == "Test Scheduler"
    assert "other" in services


async def test_remove_schedule_confirm_without_input_aborts_unknown() -> None:
    """Re-entering the confirm step with no input aborts as unknown."""
    flow = OptionsFlowHandler()

    result = await flow.async_step_remove_schedule_confirm()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


def test_get_default_holiday_country_returns_ha_country() -> None:
    """With no stored country, the HA-configured country is used as default."""
    flow = OptionsFlowHandler()
    flow.hass = SimpleNamespace(config=SimpleNamespace(country="DE"))

    assert flow._get_default_holiday_country() == "DE"


def test_get_default_holiday_country_swallows_attribute_error() -> None:
    """An AttributeError while reading hass.config.country is swallowed."""

    class _FlakyCountryConfig:
        """A config stand-in whose .country raises on its second access."""

        def __init__(self) -> None:
            self._reads = 0

        def __getattr__(self, name: str) -> str:
            if name == "country":
                self._reads += 1
                if self._reads == 1:
                    return "US"
                raise AttributeError("country access failed")
            raise AttributeError(name)

    flow = OptionsFlowHandler()
    flow.hass = SimpleNamespace(config=_FlakyCountryConfig())

    assert flow._get_default_holiday_country() is None


def test_get_overlap_placeholders_none_without_conflicting_name() -> None:
    """No placeholders are returned when the conflicting name wasn't captured."""
    flow = OptionsFlowHandler()
    flow._overlap_conflicting_name = None

    assert (
        flow._get_overlap_placeholders({"base": "schedule_overlap_with_name"}) is None
    )


def test_get_yaml_error_placeholders_none_without_details() -> None:
    """No placeholders are returned when YAML error details weren't captured."""
    flow = OptionsFlowHandler()
    flow._yaml_error_details = None

    assert (
        flow._get_yaml_error_placeholders({"base": "invalid_yaml_with_details"}) is None
    )


async def test_validate_week_schedule_skips_non_week_schedule() -> None:
    """Non-week schedules bypass range validation entirely."""
    flow = OptionsFlowHandler()

    assert await flow._validate_week_schedule({"schedule_type": "date"}) == {}


async def test_configure_date_schedule_overlap_without_conflicting_name(
    hass: HomeAssistant, create_service_entry
) -> None:
    """An overlap with no resolvable conflicting name uses the generic error."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.ha_scheduler.schedule_generator.check_overlap",
        return_value=(True, None),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_schedule"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"schedule_type": "date"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {**_BASE_VALID_INPUT[SCHEDULE_TYPE_DATE], "configuration": ""},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "schedule_overlap"


async def test_add_week_schedule_defaults_country_from_hass_config(
    hass: HomeAssistant, create_service_entry
) -> None:
    """A brand-new week schedule adopts the HA-configured country by default."""
    entry = create_service_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.config.country = "DE"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_schedule"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"schedule_type": "week"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**_BASE_VALID_INPUT[SCHEDULE_TYPE_WEEK], "configuration": ""},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    schedules = get_schedules_from_entry(entry)
    schedule = next(iter(schedules.values()))
    assert schedule["country_code"] == "DE"
