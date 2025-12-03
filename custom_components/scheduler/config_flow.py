"""Config flow for Scheduler integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, MONTHS

_LOGGER = logging.getLogger(__name__)

# Month options with proper labels
MONTH_OPTIONS = [
    SelectOptionDict(value=month, label=month.capitalize())
    for month in MONTHS
]


def get_month_selector(default: str) -> SelectSelector:
    """Get a month selector with proper labels."""
    return SelectSelector(
        SelectSelectorConfig(
            options=MONTH_OPTIONS,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="My Schedule"): str,
        vol.Required("start_month", default="january"): get_month_selector("january"),
        vol.Required("end_month", default="december"): get_month_selector("december"),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""
    start_month_idx = MONTHS.index(data["start_month"])
    end_month_idx = MONTHS.index(data["end_month"])

    if start_month_idx > end_month_idx:
        raise ValueError("Start month must be before or equal to end month")

    return {"title": data["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Scheduler."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ValueError:
                _LOGGER.warning("Start month must be before end month")
                errors["base"] = "invalid_month_range"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
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
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except ValueError:
                _LOGGER.warning("Start month must be before end month")
                errors["base"] = "invalid_month_range"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Update config entry data
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=user_input,
                    title=user_input["name"],
                )
                return self.async_create_entry(title="", data={})

        # Pre-fill with current values
        current_data = self.config_entry.data
        schema = vol.Schema(
            {
                vol.Required("name", default=current_data.get("name", "My Schedule")): str,
                vol.Required(
                    "start_month", default=current_data.get("start_month", "january")
                ): get_month_selector(current_data.get("start_month", "january")),
                vol.Required(
                    "end_month", default=current_data.get("end_month", "december")
                ): get_month_selector(current_data.get("end_month", "december")),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
