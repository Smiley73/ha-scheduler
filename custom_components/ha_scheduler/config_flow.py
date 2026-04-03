"""Config flow for Scheduler integration."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
import yaml
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, UnknownEntry
from homeassistant.core import callback
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

from .const import DAY_NAMES, DOMAIN, MONTH_NAMES

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
    """Get occurrence options with week type support for week schedules."""
    from .const import WEEK_OCCURRENCE_OPTIONS

    return [
        SelectOptionDict(value=value, label=label.capitalize())
        for value, label in WEEK_OCCURRENCE_OPTIONS
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

    VERSION = 2
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            raw_name = user_input.get("scheduler_name", "Scheduler")
            name = raw_name.strip() if isinstance(raw_name, str) else "Scheduler"

            if not name:
                errors["scheduler_name"] = "empty_scheduler_name"
            else:
                # Check for duplicate scheduler names
                existing_entries = self._async_current_entries()
                if any(
                    entry.title.lower() == name.lower() for entry in existing_entries
                ):
                    errors["scheduler_name"] = "duplicate_scheduler_name"
                else:
                    return self.async_create_entry(
                        title=name,
                        data={"scheduler_name": name},
                        options={
                            "services": {
                                "default": {
                                    "name": name,
                                    "schedules": {},
                                    "configuration": {},
                                }
                            }
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("scheduler_name", default="Scheduler"): str,
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
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Scheduler."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._schedule_id: str | None = (
            None  # UUID of the schedule being added or edited
        )
        self._schedule_data: dict[
            str, Any
        ] = {}  # Form defaults for the active schedule step
        self._service_id: str = "default"  # Default service for now
        self._holiday_data: dict[
            str, Any
        ] = {}  # State carried across the multi-step holiday import flow
        # Populated by _validate_schedule_conflicts to carry the conflicting schedule's
        # name into the error placeholder shown to the user.
        self._overlap_conflicting_name: str | None = None
        # Populated when YAML parsing fails so the error message can include details.
        self._yaml_error_details: str | None = None

    def _get_service_schedules(self) -> dict[str, Any]:
        """Get schedules for the current service."""
        entry = self.hass.config_entries.async_get_entry(self.config_entry.entry_id)
        if not entry:
            return {}

        # Handle both new service-based structure and legacy structure
        services = entry.options.get("services", {})
        if services:
            return services.get(self._service_id, {}).get("schedules", {})
        else:
            # Legacy structure
            return entry.options.get("schedules", {})

    def _update_service_schedules(self, schedules: dict[str, Any]) -> dict[str, Any]:
        """Update schedules for the current service and return updated options."""
        entry = self.hass.config_entries.async_get_entry(self.config_entry.entry_id)
        if not entry:
            return {}

        # Handle both new service-based structure and legacy structure
        services = entry.options.get("services", {})
        if services:
            # New service-based structure
            new_services = dict(services)

            # Ensure service exists
            if self._service_id not in new_services:
                new_services[self._service_id] = {
                    "name": entry.title,
                    "schedules": {},
                    "configuration": {},
                }

            new_services[self._service_id] = {
                **new_services[self._service_id],
                "schedules": schedules,
            }

            return {**entry.options, "services": new_services}
        else:
            # Legacy structure - update directly
            return {**entry.options, "schedules": schedules}

    def _get_overlap_placeholders(
        self, errors: dict[str, str]
    ) -> dict[str, str] | None:
        """Return placeholders for overlap errors when available."""
        if errors.get("base") != "schedule_overlap_with_name":
            return None
        if not self._overlap_conflicting_name:
            return None
        return {"conflicting_schedule": self._overlap_conflicting_name}

    def _get_yaml_error_placeholders(
        self, errors: dict[str, str]
    ) -> dict[str, str] | None:
        """Return placeholders for YAML validation errors when available."""
        if errors.get("base") != "invalid_yaml_with_details":
            return None
        if not self._yaml_error_details:
            return None
        return {"details": self._yaml_error_details}

    def _get_error_placeholders(self, errors: dict[str, str]) -> dict[str, str] | None:
        """Return placeholders for the current error state when available."""
        placeholders: dict[str, str] = {}
        if overlap_placeholders := self._get_overlap_placeholders(errors):
            placeholders.update(overlap_placeholders)
        if yaml_placeholders := self._get_yaml_error_placeholders(errors):
            placeholders.update(yaml_placeholders)
        return placeholders or None

    def _validate_schedule_conflicts(
        self, data: dict[str, Any], schedules: dict[str, Any]
    ) -> dict[str, str]:
        """Check for duplicate names and date overlaps against existing schedules.

        Returns an errors dict (empty when there are no conflicts).
        """
        from .schedule_generator import check_overlap

        errors: dict[str, str] = {}
        self._overlap_conflicting_name = None

        # Check for duplicate schedule names
        schedule_name = data["name"].strip().lower()
        for sid, schedule in schedules.items():
            if (
                sid != self._schedule_id
                and schedule["name"].strip().lower() == schedule_name
            ):
                errors["name"] = "duplicate_name"
                break

        if not errors:
            has_overlap, conflicting_name = check_overlap(
                data,
                list(schedules.values()),
                # When editing, exclude the current schedule so it doesn't conflict with itself.
                # When adding, _schedule_id is a new UUID not yet in schedules, so exclude_uid=None.
                exclude_uid=self._schedule_id
                if self._schedule_id in schedules
                else None,
            )

            if has_overlap:
                _LOGGER.debug(
                    "Schedule overlaps with existing schedule: %s", conflicting_name
                )
                self._overlap_conflicting_name = conflicting_name
                if conflicting_name:
                    errors["base"] = "schedule_overlap_with_name"
                else:
                    errors["base"] = "schedule_overlap"

        return errors

    def _validate_week_schedule(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate that a week schedule produces a valid recurring range."""
        if data.get("schedule_type") != "week":
            return {}

        from .schedule_generator import week_schedule_has_valid_ranges

        if week_schedule_has_valid_ranges(data):
            return {}

        return {"base": "invalid_week_schedule"}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_schedule",
                "edit_schedule",
                "remove_schedule",
                "import_holidays",
                "default_configuration",
            ],
        )

    async def async_step_add_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Configure date-based schedule (single page)."""
        self._yaml_error_details = None
        errors: dict[str, str] = {}

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

                # Get current schedules and validate for conflicts
                schedules = self._get_service_schedules()
                errors.update(self._validate_schedule_conflicts(data, schedules))

                if not errors:
                    # Save schedule
                    new_schedules = dict(schedules)
                    new_schedules[self._schedule_id] = data
                    updated_options = self._update_service_schedules(new_schedules)

                    return self.async_create_entry(title="", data=updated_options)

            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                details = str(err).strip()
                self._yaml_error_details = details or None
                errors["base"] = (
                    "invalid_yaml_with_details" if details else "invalid_yaml"
                )
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
            description_placeholders=self._get_error_placeholders(errors),
        )

    async def async_step_configure_week(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure week-based schedule (single page)."""
        self._yaml_error_details = None
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Parse start week (may include type for first week)
                start_week_value = user_input["start_week"]
                if "_" in start_week_value:
                    start_week, start_week_type = start_week_value.split("_", 1)
                    start_week = int(start_week)
                else:
                    start_week = int(start_week_value)
                    start_week_type = "partial"  # Default for non-first weeks

                # Parse end week (may include type for first week)
                end_week_value = user_input["end_week"]
                if "_" in end_week_value:
                    end_week, end_week_type = end_week_value.split("_", 1)
                    end_week = int(end_week)
                else:
                    end_week = int(end_week_value)
                    end_week_type = "partial"  # Default for non-first weeks

                data = {
                    "name": user_input["name"],
                    "schedule_type": "week",
                    "start_month": int(user_input["start_month"]),
                    "start_week": start_week,
                    "end_month": int(user_input["end_month"]),
                    "end_week": end_week,
                    "uid": self._schedule_id,
                }

                # Add week types if they're for first week (occurrence 0)
                if start_week == 0:
                    data["start_week_type"] = start_week_type
                if end_week == 0:
                    data["end_week_type"] = end_week_type

                # Add day of week fields only if they are specified (not empty)
                if (
                    user_input.get("start_day_of_week")
                    and user_input["start_day_of_week"] != ""
                ):
                    data["start_day_of_week"] = int(user_input["start_day_of_week"])

                if (
                    user_input.get("end_day_of_week")
                    and user_input["end_day_of_week"] != ""
                ):
                    data["end_day_of_week"] = int(user_input["end_day_of_week"])

                # Add country code if available from Home Assistant config
                try:
                    if (
                        hasattr(self.hass.config, "country")
                        and self.hass.config.country
                    ):
                        data["country_code"] = self.hass.config.country
                except AttributeError:
                    # Fallback - try to get from locale or default to None
                    pass

                config_yaml = user_input.get("configuration") or ""
                config_yaml = (
                    config_yaml.strip() if isinstance(config_yaml, str) else ""
                )
                if config_yaml:
                    config_dict = _validate_yaml_config(config_yaml)
                    if config_dict:
                        data["configuration"] = config_dict

                errors.update(self._validate_week_schedule(data))

                # Get current schedules and validate for conflicts
                if not errors:
                    schedules = self._get_service_schedules()
                    errors.update(self._validate_schedule_conflicts(data, schedules))

                if not errors:
                    new_schedules = dict(schedules)
                    new_schedules[self._schedule_id] = data
                    updated_options = self._update_service_schedules(new_schedules)

                    return self.async_create_entry(title="", data=updated_options)

            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                details = str(err).strip()
                self._yaml_error_details = details or None
                errors["base"] = (
                    "invalid_yaml_with_details" if details else "invalid_yaml"
                )
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

        # Convert stored week values back to combined format for display
        start_week_default = defaults.get("start_week", 0)
        start_week_type = defaults.get("start_week_type", "partial")
        if start_week_default == 0:
            start_week_display = f"{start_week_default}_{start_week_type}"
        else:
            start_week_display = str(start_week_default)

        end_week_default = defaults.get("end_week", 4)
        end_week_type = defaults.get("end_week_type", "partial")
        if end_week_default == 0:
            end_week_display = f"{end_week_default}_{end_week_type}"
        else:
            end_week_display = str(end_week_default)

        schema_dict = {
            vol.Required("name", default=defaults.get("name", "My Schedule")): str,
            vol.Required(
                "start_month", default=str(defaults.get("start_month", 1))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_month_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("start_week", default=start_week_display): SelectSelector(
                SelectSelectorConfig(
                    options=_get_occurrence_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional(
                "start_day_of_week", default=str(defaults.get("start_day_of_week", ""))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[SelectOptionDict(value="", label="Whole week")]
                    + _get_day_of_week_options(),
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                "end_month", default=str(defaults.get("end_month", 12))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_month_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("end_week", default=end_week_display): SelectSelector(
                SelectSelectorConfig(
                    options=_get_occurrence_options(), mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional(
                "end_day_of_week", default=str(defaults.get("end_day_of_week", ""))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[SelectOptionDict(value="", label="Whole week")]
                    + _get_day_of_week_options(),
                    mode=SelectSelectorMode.DROPDOWN,
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
            description_placeholders=self._get_error_placeholders(errors),
        )

    async def async_step_configure_nth_day(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure nth-day schedule (single page)."""
        self._yaml_error_details = None
        errors: dict[str, str] = {}

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

                # Get current schedules and validate for conflicts
                schedules = self._get_service_schedules()
                errors.update(self._validate_schedule_conflicts(data, schedules))

                if not errors:
                    new_schedules = dict(schedules)
                    new_schedules[self._schedule_id] = data
                    updated_options = self._update_service_schedules(new_schedules)

                    return self.async_create_entry(title="", data=updated_options)

            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                details = str(err).strip()
                self._yaml_error_details = details or None
                errors["base"] = (
                    "invalid_yaml_with_details" if details else "invalid_yaml"
                )
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
            description_placeholders=self._get_error_placeholders(errors),
        )

    async def async_step_edit_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a schedule to edit."""
        schedules = self._get_service_schedules()

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
    ) -> ConfigFlowResult:
        """Remove a schedule."""
        schedules = self._get_service_schedules()

        if not schedules:
            return self.async_abort(reason="no_schedules")

        if user_input is not None:
            self._schedule_id = user_input["schedule_id"]
            schedule = schedules[self._schedule_id]

            return self.async_show_form(
                step_id="remove_schedule_confirm",
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

    async def async_step_remove_schedule_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm schedule removal."""
        schedules = self._get_service_schedules()

        if user_input is not None:
            if user_input.get("confirm"):
                # Remove schedule
                new_schedules = dict(schedules)
                new_schedules.pop(self._schedule_id, None)
                updated_options = self._update_service_schedules(new_schedules)

                return self.async_create_entry(title="", data=updated_options)

            return self.async_abort(reason="not_confirmed")

        # This should not happen as we redirect here from remove_schedule
        return self.async_abort(reason="unknown")

    async def async_step_default_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure default configuration."""
        self._yaml_error_details = None
        errors: dict[str, str] = {}

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
                try:
                    entry_id = self.config_entry.entry_id
                    entry = self.hass.config_entries.async_get_entry(entry_id)
                except UnknownEntry:
                    errors["base"] = "entry_not_found"
                    return self.async_show_form(
                        step_id="default_configuration",
                        data_schema=vol.Schema(
                            {
                                vol.Optional(
                                    "configuration", default=""
                                ): TemplateSelector(),
                            }
                        ),
                        errors=errors,
                    )

                if not entry:
                    errors["base"] = "entry_not_found"
                    return self.async_show_form(
                        step_id="default_configuration",
                        data_schema=vol.Schema(
                            {
                                vol.Optional(
                                    "configuration", default=""
                                ): TemplateSelector(),
                            }
                        ),
                        errors=errors,
                    )

                services = entry.options.get("services", {})
                new_services = dict(services)

                # Ensure service exists
                if self._service_id not in new_services:
                    new_services[self._service_id] = {
                        "name": entry.title,
                        "schedules": {},
                        "configuration": {},
                    }

                new_services[self._service_id] = {
                    **new_services[self._service_id],
                    "configuration": config_dict or {},
                }

                updated_options = {**entry.options, "services": new_services}

                return self.async_create_entry(title="", data=updated_options)

            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                details = str(err).strip()
                self._yaml_error_details = details or None
                errors["base"] = (
                    "invalid_yaml_with_details" if details else "invalid_yaml"
                )
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

        # Get current service configuration
        entry = self.hass.config_entries.async_get_entry(self.config_entry.entry_id)
        services = entry.options.get("services", {}) if entry else {}
        current_config = services.get(self._service_id, {}).get("configuration", {})
        config_str = yaml.dump(current_config) if current_config else ""

        # If re-displaying after an error, preserve what the user typed so they can correct it
        if user_input is not None and errors:
            config_str = user_input.get("configuration") or ""

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
            description_placeholders=self._get_error_placeholders(errors),
        )

    async def async_step_import_holidays(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import holidays - step 1: select country."""
        if user_input is not None:
            self._holiday_data = {"country": user_input["country"]}
            return await self.async_step_import_holidays_categories()

        try:
            from .holiday_importer import get_supported_countries

            countries = await get_supported_countries()

            if not countries:
                return self.async_abort(reason="no_countries_available")

            country_options = [
                SelectOptionDict(value=code, label=name)
                for code, name in sorted(countries.items(), key=lambda x: x[1])
            ]

            return self.async_show_form(
                step_id="import_holidays",
                data_schema=vol.Schema(
                    {
                        vol.Required("country"): SelectSelector(
                            SelectSelectorConfig(
                                options=country_options,
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    }
                ),
            )
        except Exception as e:
            _LOGGER.error("Failed to load countries: %s", e)
            return self.async_abort(reason="import_error")

    async def async_step_import_holidays_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import holidays - step 2: select categories."""
        if user_input is not None:
            self._holiday_data["categories"] = user_input.get("categories", ["public"])
            return await self.async_step_import_holidays_select()

        try:
            from .holiday_importer import get_available_categories

            country = self._holiday_data.get("country")
            if not country:
                return self.async_abort(reason="import_error")
            categories = await get_available_categories(country)

            if not categories:
                # Skip to next step with default
                self._holiday_data["categories"] = ["public"]
                return await self.async_step_import_holidays_select()

            category_options = [
                SelectOptionDict(value=code, label=name)
                for code, name in categories.items()
            ]

            return self.async_show_form(
                step_id="import_holidays_categories",
                data_schema=vol.Schema(
                    {
                        vol.Optional("categories", default=["public"]): SelectSelector(
                            SelectSelectorConfig(
                                options=category_options,
                                mode=SelectSelectorMode.LIST,
                                multiple=True,
                            )
                        ),
                    }
                ),
                description_placeholders={"country": self._holiday_data["country"]},
            )
        except Exception as e:
            _LOGGER.error("Failed to load categories: %s", e)
            return self.async_abort(reason="import_error")

    async def async_step_import_holidays_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import holidays - step 3: select specific holidays."""
        if user_input is not None:
            selected_holidays = user_input.get("holidays", [])
            overwrite_existing = user_input.get("overwrite_existing", False)
            skip_on_overlap = user_input.get("skip_on_overlap", True)
            include_country_name = user_input.get("include_country_name", False)

            if not selected_holidays:
                return self.async_show_form(
                    step_id="import_holidays_select",
                    data_schema=await self._get_holiday_selection_schema(),
                    errors={"holidays": "no_holidays_selected"},
                )

            return await self._import_selected_holidays(
                selected_holidays,
                overwrite_existing,
                skip_on_overlap,
                include_country_name,
            )

        return self.async_show_form(
            step_id="import_holidays_select",
            data_schema=await self._get_holiday_selection_schema(),
        )

    async def _get_holiday_selection_schema(self) -> vol.Schema:
        """Get the schema for holiday selection."""
        try:
            from .holiday_importer import get_holidays_for_country

            # Ensure _holiday_data is initialized
            if not hasattr(self, "_holiday_data") or not self._holiday_data:
                return vol.Schema(
                    {
                        vol.Optional("holidays", default=[]): SelectSelector(
                            SelectSelectorConfig(options=[], multiple=True)
                        ),
                    }
                )

            country = self._holiday_data.get("country")
            categories = self._holiday_data.get("categories", ["public"])

            if not country:
                return vol.Schema(
                    {
                        vol.Optional("holidays", default=[]): SelectSelector(
                            SelectSelectorConfig(options=[], multiple=True)
                        ),
                    }
                )

            holidays_data = await get_holidays_for_country(country, categories)

            _LOGGER.debug(
                "Got %d holidays for country %s, categories %s",
                len(holidays_data) if holidays_data else 0,
                country,
                categories,
            )

            if not holidays_data:
                return vol.Schema(
                    {
                        vol.Optional("holidays", default=[]): SelectSelector(
                            SelectSelectorConfig(options=[], multiple=True)
                        ),
                    }
                )

            # Create options with pattern descriptions
            holiday_options = []
            for holiday_name, holiday_info in sorted(holidays_data.items()):
                if holiday_info is None:
                    _LOGGER.warning("Holiday info is None for %s", holiday_name)
                    continue

                pattern = holiday_info.get("pattern")
                if pattern is None:
                    _LOGGER.warning("Pattern is None for %s", holiday_name)
                    description = "No pattern available"
                else:
                    description = pattern.get("description", "Unknown pattern")

                label = f"{holiday_name} ({description})"
                holiday_options.append(
                    SelectOptionDict(value=holiday_name, label=label)
                )

            # Get all holiday names for default selection
            all_holiday_names = [option["value"] for option in holiday_options]

            return vol.Schema(
                {
                    vol.Optional("holidays", default=all_holiday_names): SelectSelector(
                        SelectSelectorConfig(
                            options=holiday_options,
                            mode=SelectSelectorMode.LIST,
                            multiple=True,
                        )
                    ),
                    vol.Optional("overwrite_existing", default=False): bool,
                    vol.Optional("skip_on_overlap", default=True): bool,
                    vol.Optional("include_country_name", default=False): bool,
                }
            )

        except Exception as e:
            _LOGGER.error("Failed to get holidays: %s", e)
            return vol.Schema(
                {
                    vol.Optional("holidays", default=[]): SelectSelector(
                        SelectSelectorConfig(options=[], multiple=True)
                    ),
                }
            )

    async def _import_selected_holidays(
        self,
        selected_holidays: list[str],
        overwrite_existing: bool,
        skip_on_overlap: bool,
        include_country_name: bool = False,
    ) -> ConfigFlowResult:
        """Import the selected holidays as schedules."""
        try:
            from .holiday_importer import get_holidays_for_country
            from .schedule_generator import check_overlap

            country = self._holiday_data.get("country")
            categories = self._holiday_data.get("categories", ["public"])

            if not country:
                return self.async_abort(reason="import_error")

            all_holidays = await get_holidays_for_country(country, categories)

            # Get current schedules
            schedules = self._get_service_schedules()
            new_schedules = dict(schedules)

            imported_count = 0
            skipped_count = 0
            overwritten_count = 0
            errors = []

            for holiday_name in selected_holidays:
                if holiday_name not in all_holidays:
                    errors.append(f"Holiday '{holiday_name}' not found")
                    continue

                holiday_info = all_holidays[holiday_name]
                pattern = holiday_info.get("pattern")

                if not pattern:
                    errors.append(f"Could not determine pattern for '{holiday_name}'")
                    continue

                # Create schedule from pattern
                if include_country_name:
                    schedule_name = f"{holiday_name} ({country})"
                else:
                    schedule_name = holiday_name
                schedule = {
                    "uid": str(uuid.uuid4()),
                    "name": schedule_name,
                    **{k: v for k, v in pattern.items() if k != "description"},
                }

                # Check for existing schedule with same name
                existing_schedule_id = None
                for sid, existing_schedule in new_schedules.items():
                    if existing_schedule["name"].lower() == schedule_name.lower():
                        existing_schedule_id = sid
                        break

                excluded_uid = None
                if existing_schedule_id:
                    if overwrite_existing:
                        # Validate the replacement against the rest of the schedules
                        # before committing the overwrite.
                        schedule["uid"] = existing_schedule_id
                        excluded_uid = existing_schedule_id
                    else:
                        # Skip existing
                        skipped_count += 1
                        errors.append(
                            f"Schedule '{schedule_name}' already exists (skipped)"
                        )
                        continue

                has_overlap, conflicting_name = check_overlap(
                    schedule,
                    list(new_schedules.values()),
                    exclude_uid=excluded_uid,
                )

                if has_overlap and skip_on_overlap:
                    skipped_count += 1
                    errors.append(
                        f"Holiday '{holiday_name}' overlaps with '{conflicting_name}' (skipped)"
                    )
                    continue

                if existing_schedule_id and overwrite_existing:
                    new_schedules[existing_schedule_id] = schedule
                    overwritten_count += 1
                    continue

                # Add the schedule (importing despite overlap when skip_on_overlap is False)
                new_schedules[schedule["uid"]] = schedule
                imported_count += 1

            # Update schedules if any were imported or overwritten
            if imported_count > 0 or overwritten_count > 0:
                updated_options = self._update_service_schedules(new_schedules)

                # Create success message
                messages = []
                if imported_count > 0:
                    messages.append(f"Imported {imported_count} holiday(s)")
                if overwritten_count > 0:
                    messages.append(
                        f"Overwritten {overwritten_count} existing schedule(s)"
                    )
                if skipped_count > 0:
                    messages.append(f"Skipped {skipped_count} holiday(s)")

                return self.async_create_entry(title="", data=updated_options)
            else:
                # Nothing was imported - all selected holidays were skipped or errored
                _LOGGER.debug("No holidays imported. Details: %s", errors)
                return self.async_show_form(
                    step_id="import_holidays_select",
                    data_schema=await self._get_holiday_selection_schema(),
                    errors={"base": "no_holidays_imported"},
                )

        except Exception:
            _LOGGER.exception("Failed to import holidays")
            return self.async_show_form(
                step_id="import_holidays_select",
                data_schema=await self._get_holiday_selection_schema(),
                errors={"base": "import_error"},
            )
