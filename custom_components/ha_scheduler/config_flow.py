"""Config flow for Scheduler integration."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
import yaml
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)

from .const import DAY_NAMES, DOMAIN, MONTH_NAMES, OCCURRENCE_NAMES

_LOGGER = logging.getLogger(__name__)


def _get_month_options() -> list[SelectOptionDict]:
    """Get month options (values are integers 1-12)."""
    return [
        SelectOptionDict(value=str(i + 1), label=MONTH_NAMES[i].capitalize())
        for i in range(12)
    ]


def _get_day_of_week_options() -> list[SelectOptionDict]:
    """Get day of week options (values are integers 0-6)."""
    return [
        SelectOptionDict(value=str(i), label=DAY_NAMES[i].capitalize())
        for i in range(7)
    ]


def _get_occurrence_options() -> list[SelectOptionDict]:
    """Get occurrence options (values are integers 0-4)."""
    return [
        SelectOptionDict(value=str(i), label=OCCURRENCE_NAMES[i].capitalize())
        for i in range(5)
    ]


def _validate_yaml_config(yaml_str: str) -> dict | None:
    """Validate YAML configuration string.

    Returns parsed dict if valid, raises ValueError if invalid.
    """
    if not yaml_str or not yaml_str.strip():
        return None

    try:
        parsed = yaml.safe_load(yaml_str)
        if not isinstance(parsed, dict):
            raise ValueError(
                "Configuration must be a YAML dictionary, not a simple value"
            )
        return parsed
    except yaml.YAMLError as err:
        raise ValueError(f"Invalid YAML: {err}") from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Scheduler."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            name = user_input.get("name", "Scheduler").strip()

            # Check for duplicate scheduler names
            existing_entries = self._async_current_entries()
            if any(entry.title.lower() == name.lower() for entry in existing_entries):
                errors["name"] = "Name already exists. Please choose a different name."
            else:
                return self.async_create_entry(
                    title=name,
                    data={},
                    options={"schedules": {}},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("name", default="Scheduler"): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Scheduler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._schedule_id: str | None = None
        self._schedule_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_schedule",
                "edit_schedule",
                "remove_schedule",
                "default_configuration",
            ],
        )

    async def async_step_add_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new schedule - select type first."""
        if user_input is not None:
            self._schedule_data = {"schedule_type": user_input["schedule_type"]}
            self._schedule_id = str(uuid.uuid4())

            if user_input["schedule_type"] == "date":
                return await self.async_step_configure_date()
            if user_input["schedule_type"] == "week":
                return await self.async_step_configure_week()
            return await self.async_step_configure_nth_day()

        return self.async_show_form(
            step_id="add_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule_type", default="date"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="date", label="By Date"),
                                SelectOptionDict(
                                    value="week", label="By Week of Month"
                                ),
                                SelectOptionDict(
                                    value="nth-day", label="By Nth Day of Month"
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_configure_date(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure date-based schedule (single page)."""
        errors = {}

        if user_input is not None:
            try:
                # Convert string values to integers
                data = {
                    "name": user_input["name"],
                    "schedule_type": "date",
                    "start_month": int(user_input["start_month"]),
                    "start_day": int(user_input["start_day"]),
                    "end_month": int(user_input["end_month"]),
                    "end_day": int(user_input["end_day"]),
                    "uid": self._schedule_id,
                }

                # Validate and parse configuration
                config_yaml = user_input.get("configuration") or ""
                config_yaml = (
                    config_yaml.strip() if isinstance(config_yaml, str) else ""
                )
                if config_yaml:
                    config_dict = _validate_yaml_config(config_yaml)
                    if config_dict:
                        data["configuration"] = config_dict
                # If configuration is empty, explicitly don't include the key in data

                # Check for overlaps and name conflicts - get fresh options from config entries
                entry = self.hass.config_entries.async_get_entry(
                    self.config_entry.entry_id
                )
                schedules = entry.options.get("schedules", {}) if entry else {}

                # Check for duplicate schedule names
                schedule_name = data["name"].strip().lower()
                for sid, schedule in schedules.items():
                    if (
                        sid != self._schedule_id
                        and schedule["name"].strip().lower() == schedule_name
                    ):
                        errors["name"] = (
                            "A schedule with this name already exists. Please choose a different name."
                        )
                        break

                if not errors:
                    from .schedule_generator import check_overlap

                    has_overlap, conflicting_name = check_overlap(
                        data,
                        list(schedules.values()),
                        exclude_uid=self._schedule_id
                        if self._schedule_id in schedules
                        else None,
                    )

                    if has_overlap:
                        errors["base"] = (
                            f"This schedule overlaps with '{conflicting_name}'"
                        )

                if not errors:
                    # Save schedule
                    new_schedules = dict(schedules)
                    new_schedules[self._schedule_id] = data

                    # Get fresh entry again before update to ensure we have latest options
                    entry = self.hass.config_entries.async_get_entry(
                        self.config_entry.entry_id
                    )
                    updated_options = {**entry.options, "schedules": new_schedules}

                    return self.async_create_entry(title="", data=updated_options)

            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                errors["base"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

        # Use user_input for defaults if available (when re-displaying after error), otherwise use stored schedule data
        defaults = user_input if user_input and errors else self._schedule_data
        # Convert configuration dict back to YAML string for display
        config_value = defaults.get("configuration", "")
        if isinstance(config_value, dict):
            config_value = yaml.dump(
                config_value, default_flow_style=False, sort_keys=False
            ).strip()

        # Only use config_value as placeholder, not as default (to allow clearing)
        schema_dict = {
            vol.Required("name", default=defaults.get("name", "My Schedule")): str,
            vol.Required(
                "start_month", default=str(defaults.get("start_month", 1))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_month_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "start_day", default=defaults.get("start_day", 1)
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=31, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                "end_month", default=str(defaults.get("end_month", 12))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_month_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "end_day", default=defaults.get("end_day", 31)
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=31, mode=NumberSelectorMode.BOX)
            ),
        }

        # Add configuration field with default value
        schema_dict[vol.Optional("configuration", default=config_value)] = (
            TemplateSelector()
        )

        return self.async_show_form(
            step_id="configure_date",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_configure_week(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure week-based schedule (single page)."""
        errors = {}

        if user_input is not None:
            try:
                data = {
                    "name": user_input["name"],
                    "schedule_type": "week",
                    "start_month": int(user_input["start_month"]),
                    "start_week": int(user_input["start_week"]),
                    "start_day_of_week": int(user_input["start_day_of_week"]),
                    "end_month": int(user_input["end_month"]),
                    "end_week": int(user_input["end_week"]),
                    "end_day_of_week": int(user_input["end_day_of_week"]),
                    "uid": self._schedule_id,
                }

                config_yaml = user_input.get("configuration") or ""
                config_yaml = (
                    config_yaml.strip() if isinstance(config_yaml, str) else ""
                )
                if config_yaml:
                    config_dict = _validate_yaml_config(config_yaml)
                    if config_dict:
                        data["configuration"] = config_dict

                # Get fresh options from config entries
                entry = self.hass.config_entries.async_get_entry(
                    self.config_entry.entry_id
                )
                schedules = entry.options.get("schedules", {}) if entry else {}

                # Check for duplicate schedule names
                schedule_name = data["name"].strip().lower()
                for sid, schedule in schedules.items():
                    if (
                        sid != self._schedule_id
                        and schedule["name"].strip().lower() == schedule_name
                    ):
                        errors["name"] = (
                            "A schedule with this name already exists. Please choose a different name."
                        )
                        break

                if not errors:
                    from .schedule_generator import check_overlap

                    has_overlap, conflicting_name = check_overlap(
                        data,
                        list(schedules.values()),
                        exclude_uid=self._schedule_id
                        if self._schedule_id in schedules
                        else None,
                    )

                    if has_overlap:
                        errors["base"] = (
                            f"This schedule overlaps with '{conflicting_name}'"
                        )

                if not errors:
                    new_schedules = dict(schedules)
                    new_schedules[self._schedule_id] = data

                    # Get fresh entry again before update
                    entry = self.hass.config_entries.async_get_entry(
                        self.config_entry.entry_id
                    )
                    updated_options = {**entry.options, "schedules": new_schedules}

                    return self.async_create_entry(title="", data=updated_options)

            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                errors["base"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

        # Use user_input for defaults if available (when re-displaying after error), otherwise use stored schedule data
        defaults = user_input if user_input and errors else self._schedule_data
        # Convert configuration dict back to YAML string for display
        config_value = defaults.get("configuration", "")
        if isinstance(config_value, dict):
            config_value = yaml.dump(
                config_value, default_flow_style=False, sort_keys=False
            ).strip()

        schema_dict = {
            vol.Required("name", default=defaults.get("name", "My Schedule")): str,
            vol.Required(
                "start_month", default=str(defaults.get("start_month", 1))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_month_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "start_week", default=str(defaults.get("start_week", 0))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_occurrence_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "start_day_of_week", default=str(defaults.get("start_day_of_week", 0))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_day_of_week_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "end_month", default=str(defaults.get("end_month", 12))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_month_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "end_week", default=str(defaults.get("end_week", 4))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_occurrence_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "end_day_of_week", default=str(defaults.get("end_day_of_week", 6))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_day_of_week_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
        }

        schema_dict[vol.Optional("configuration", default=config_value)] = (
            TemplateSelector()
        )

        return self.async_show_form(
            step_id="configure_week",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_configure_nth_day(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure nth-day schedule (single page)."""
        errors = {}

        if user_input is not None:
            try:
                data = {
                    "name": user_input["name"],
                    "schedule_type": "nth-day",
                    "month": int(user_input["month"]),
                    "occurrence": int(user_input["occurrence"]),
                    "day_of_week": int(user_input["day_of_week"]),
                    "start_offset": int(user_input["start_offset"]),
                    "end_offset": int(user_input["end_offset"]),
                    "uid": self._schedule_id,
                }

                config_yaml = user_input.get("configuration") or ""
                config_yaml = (
                    config_yaml.strip() if isinstance(config_yaml, str) else ""
                )
                if config_yaml:
                    config_dict = _validate_yaml_config(config_yaml)
                    if config_dict:
                        data["configuration"] = config_dict

                # Get fresh options from config entries
                entry = self.hass.config_entries.async_get_entry(
                    self.config_entry.entry_id
                )
                schedules = entry.options.get("schedules", {}) if entry else {}

                # Check for duplicate schedule names
                schedule_name = data["name"].strip().lower()
                for sid, schedule in schedules.items():
                    if (
                        sid != self._schedule_id
                        and schedule["name"].strip().lower() == schedule_name
                    ):
                        errors["name"] = (
                            "A schedule with this name already exists. Please choose a different name."
                        )
                        break

                if not errors:
                    from .schedule_generator import check_overlap

                    has_overlap, conflicting_name = check_overlap(
                        data,
                        list(schedules.values()),
                        exclude_uid=self._schedule_id
                        if self._schedule_id in schedules
                        else None,
                    )

                    if has_overlap:
                        errors["base"] = (
                            f"This schedule overlaps with '{conflicting_name}'"
                        )

                if not errors:
                    new_schedules = dict(schedules)
                    new_schedules[self._schedule_id] = data

                    # Get fresh entry again before update
                    entry = self.hass.config_entries.async_get_entry(
                        self.config_entry.entry_id
                    )
                    updated_options = {**entry.options, "schedules": new_schedules}

                    return self.async_create_entry(title="", data=updated_options)

            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                errors["base"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

        # Use user_input for defaults if available (when re-displaying after error), otherwise use stored schedule data
        defaults = user_input if user_input and errors else self._schedule_data
        # Convert configuration dict back to YAML string for display
        config_value = defaults.get("configuration", "")
        if isinstance(config_value, dict):
            config_value = yaml.dump(
                config_value, default_flow_style=False, sort_keys=False
            ).strip()

        schema_dict = {
            vol.Required("name", default=defaults.get("name", "My Schedule")): str,
            vol.Required(
                "month", default=str(defaults.get("month", 1))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_month_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "occurrence", default=str(defaults.get("occurrence", 0))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_occurrence_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "day_of_week", default=str(defaults.get("day_of_week", 0))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_day_of_week_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                "start_offset", default=defaults.get("start_offset", 0)
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=30, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                "end_offset", default=defaults.get("end_offset", 0)
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=30, mode=NumberSelectorMode.BOX)
            ),
        }

        schema_dict[vol.Optional("configuration", default=config_value)] = (
            TemplateSelector()
        )

        return self.async_show_form(
            step_id="configure_nth_day",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_edit_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a schedule to edit."""
        entry = self.hass.config_entries.async_get_entry(self.config_entry.entry_id)
        schedules = entry.options.get("schedules", {}) if entry else {}

        if not schedules:
            return self.async_abort(reason="no_schedules")

        if user_input is not None:
            self._schedule_id = user_input["schedule_id"]
            schedule = schedules[self._schedule_id]
            self._schedule_data = dict(schedule)

            # Convert configuration dict to YAML string for editing
            if "configuration" in self._schedule_data and isinstance(
                self._schedule_data["configuration"], dict
            ):
                self._schedule_data["configuration"] = yaml.dump(
                    self._schedule_data["configuration"],
                    default_flow_style=False,
                    sort_keys=False,
                ).strip()

            if schedule["schedule_type"] == "date":
                return await self.async_step_configure_date()
            if schedule["schedule_type"] == "week":
                return await self.async_step_configure_week()
            return await self.async_step_configure_nth_day()

        schedule_options = [
            SelectOptionDict(value=sid, label=sdata["name"])
            for sid, sdata in sorted(
                schedules.items(), key=lambda x: x[1]["name"].lower()
            )
        ]

        return self.async_show_form(
            step_id="edit_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=schedule_options, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                }
            ),
        )

    async def async_step_remove_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a schedule."""
        entry = self.hass.config_entries.async_get_entry(self.config_entry.entry_id)
        schedules = entry.options.get("schedules", {}) if entry else {}

        if not schedules:
            return self.async_abort(reason="no_schedules")

        if self._schedule_id and user_input is not None:
            if user_input.get("confirm"):
                # Get fresh entry before update
                entry = self.hass.config_entries.async_get_entry(
                    self.config_entry.entry_id
                )
                schedules = entry.options.get("schedules", {}) if entry else {}
                new_schedules = dict(schedules)
                new_schedules.pop(self._schedule_id, None)

                updated_options = {**entry.options, "schedules": new_schedules}

                return self.async_create_entry(title="", data=updated_options)

            return self.async_abort(reason="not_confirmed")

        if user_input is not None:
            self._schedule_id = user_input["schedule_id"]
            schedule = schedules[self._schedule_id]

            return self.async_show_form(
                step_id="remove_schedule",
                data_schema=vol.Schema(
                    {
                        vol.Required("confirm", default=False): bool,
                    }
                ),
                description_placeholders={
                    "schedule_name": schedule["name"],
                    "schedule_type": schedule["schedule_type"],
                },
            )

        schedule_options = [
            SelectOptionDict(value=sid, label=sdata["name"])
            for sid, sdata in sorted(
                schedules.items(), key=lambda x: x[1]["name"].lower()
            )
        ]

        return self.async_show_form(
            step_id="remove_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=schedule_options, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                }
            ),
        )

    async def async_step_default_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure default configuration."""
        errors = {}

        if user_input is not None:
            try:
                config_yaml = user_input.get("configuration") or ""
                config_yaml = (
                    config_yaml.strip() if isinstance(config_yaml, str) else ""
                )
                config_dict = None
                if config_yaml:
                    config_dict = _validate_yaml_config(config_yaml)

                # Get fresh entry before update
                entry = self.hass.config_entries.async_get_entry(
                    self.config_entry.entry_id
                )
                updated_options = {**entry.options, "configuration": config_dict or {}}

                return self.async_create_entry(title="", data=updated_options)

            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                errors["base"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

        current_config = self.config_entry.options.get("configuration", {})
        config_str = yaml.dump(current_config) if current_config else ""

        return self.async_show_form(
            step_id="default_configuration",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "configuration", default=config_str
                    ): TemplateSelector(),
                }
            ),
            errors=errors,
        )
