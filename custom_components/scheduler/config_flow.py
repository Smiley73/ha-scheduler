"""Config flow for Scheduler integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
import yaml
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN


class SchedulerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Scheduler."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Helper integrations can allow custom names
            return self.async_create_entry(
                title=user_input["name"],
                data={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default="Scheduler"): selector.TextSelector(),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchedulerOptionsFlow:
        """Get the options flow for this handler."""
        return SchedulerOptionsFlow(config_entry)


class SchedulerOptionsFlow(OptionsFlow):
    """Handle options flow for Scheduler."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._schedule_to_edit: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "add":
                return await self.async_step_add_schedule()
            if action == "edit":
                return await self.async_step_select_schedule_to_edit()
            if action == "remove":
                return await self.async_step_select_schedule_to_remove()
            if action == "configure":
                return await self.async_step_configure()

        # Get current schedules
        schedules = self.config_entry.options.get("schedules", [])
        schedule_list = (
            "\n".join(
                f"• {s['name']}: {s['start_date']} to {s['end_date']}"
                for s in schedules
            )
            if schedules
            else "No schedules"
        )

        return self.async_show_menu(
            step_id="init",
            menu_options=["add", "edit", "remove", "configure"],
            description_placeholders={
                "schedules": schedule_list,
            },
        )

    async def async_step_add_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new schedule."""
        errors = {}

        if user_input is not None:
            schedules = list(self.config_entry.options.get("schedules", []))

            # Validate dates
            try:
                start_date = user_input["start_date"]
                end_date = user_input["end_date"]

                if end_date <= start_date:
                    errors["end_date"] = "end_before_start"
                else:
                    # Check for overlaps
                    for schedule in schedules:
                        if (
                            start_date < schedule["end_date"]
                            and end_date > schedule["start_date"]
                        ):
                            errors["base"] = "overlap"
                            break

                    if not errors:
                        schedules.append(
                            {
                                "uid": f"{self.config_entry.entry_id}_{len(schedules)}",
                                "name": user_input["name"],
                                "start_date": start_date,
                                "end_date": end_date,
                            }
                        )

                        options = dict(self.config_entry.options)
                        options["schedules"] = schedules
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            options=options,
                        )
                        return await self.async_step_init()
            except (ValueError, KeyError):
                errors["base"] = "invalid_date"

        return self.async_show_form(
            step_id="add_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): selector.TextSelector(),
                    vol.Required("start_date"): selector.DateSelector(),
                    vol.Required("end_date"): selector.DateSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_select_schedule_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a schedule to edit."""
        schedules = self.config_entry.options.get("schedules", [])

        if not schedules:
            return await self.async_step_init()

        if user_input is not None:
            self._schedule_to_edit = user_input["schedule"]
            return await self.async_step_edit_schedule()

        schedule_options = [
            selector.SelectOptionDict(
                value=s["uid"],
                label=f"{s['name']} ({s['start_date']} to {s['end_date']})",
            )
            for s in schedules
        ]

        return self.async_show_form(
            step_id="select_schedule_to_edit",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=schedule_options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_select_schedule_to_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a schedule to remove."""
        schedules = self.config_entry.options.get("schedules", [])

        if not schedules:
            return await self.async_step_init()

        if user_input is not None:
            self._schedule_to_edit = user_input["schedule"]
            return await self.async_step_remove_schedule()

        schedule_options = [
            selector.SelectOptionDict(
                value=s["uid"],
                label=f"{s['name']} ({s['start_date']} to {s['end_date']})",
            )
            for s in schedules
        ]

        return self.async_show_form(
            step_id="select_schedule_to_remove",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=schedule_options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a schedule."""
        schedules = list(self.config_entry.options.get("schedules", []))
        schedule = next(
            (s for s in schedules if s["uid"] == self._schedule_to_edit), None
        )

        if not schedule:
            return await self.async_step_init()

        errors = {}

        if user_input is not None:
            try:
                start_date = user_input["start_date"]
                end_date = user_input["end_date"]

                if end_date <= start_date:
                    errors["end_date"] = "end_before_start"
                else:
                    # Check for overlaps with other schedules
                    for other_schedule in schedules:
                        if other_schedule["uid"] == self._schedule_to_edit:
                            continue
                        if (
                            start_date < other_schedule["end_date"]
                            and end_date > other_schedule["start_date"]
                        ):
                            errors["base"] = "overlap"
                            break

                    if not errors:
                        schedule["name"] = user_input["name"]
                        schedule["start_date"] = start_date
                        schedule["end_date"] = end_date

                        options = dict(self.config_entry.options)
                        options["schedules"] = schedules
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            options=options,
                        )
                        return await self.async_step_init()
            except (ValueError, KeyError):
                errors["base"] = "invalid_date"

        return self.async_show_form(
            step_id="edit_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "name", default=schedule["name"]
                    ): selector.TextSelector(),
                    vol.Required(
                        "start_date", default=schedule["start_date"]
                    ): selector.DateSelector(),
                    vol.Required(
                        "end_date", default=schedule["end_date"]
                    ): selector.DateSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a schedule."""
        schedules = list(self.config_entry.options.get("schedules", []))
        schedule = next(
            (s for s in schedules if s["uid"] == self._schedule_to_edit), None
        )

        if not schedule:
            return await self.async_step_init()

        if user_input is not None:
            if user_input.get("confirm"):
                schedules = [s for s in schedules if s["uid"] != self._schedule_to_edit]
                options = dict(self.config_entry.options)
                options["schedules"] = schedules
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options=options,
                )
            return await self.async_step_init()

        return self.async_show_form(
            step_id="remove_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={
                "schedule_name": schedule["name"],
                "start_date": schedule["start_date"],
                "end_date": schedule["end_date"],
            },
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure advanced settings."""
        errors = {}

        current_config = self.config_entry.options.get("configuration", {})
        default_yaml = (
            yaml.dump(current_config, default_flow_style=False)
            if current_config
            else ""
        )

        if user_input is not None:
            config_yaml = user_input.get("configuration", "").strip()

            if not config_yaml:
                # Empty is allowed - clear configuration
                options = dict(self.config_entry.options)
                options["configuration"] = {}
                return self.async_create_entry(title="", data=options)

            try:
                parsed_config = yaml.safe_load(config_yaml)

                # Validate it's not a simple string
                if isinstance(parsed_config, str):
                    errors["configuration"] = "not_dict"
                elif parsed_config is None:
                    errors["configuration"] = "not_dict"
                else:
                    # Valid YAML structure
                    options = dict(self.config_entry.options)
                    options["configuration"] = parsed_config
                    return self.async_create_entry(title="", data=options)
            except yaml.YAMLError:
                errors["configuration"] = "invalid_yaml"

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "configuration", default=default_yaml
                    ): selector.TemplateSelector(),
                }
            ),
            errors=errors,
        )
