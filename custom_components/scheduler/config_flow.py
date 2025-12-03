"""Config flow for Scheduler integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, MONTHS

_LOGGER = logging.getLogger(__name__)

# Schedule type options
SCHEDULE_TYPE_OPTIONS = [
    SelectOptionDict(value="date", label="By Date"),
    SelectOptionDict(value="week", label="By Week of Month"),
]

# Month options with proper labels
MONTH_OPTIONS = [
    SelectOptionDict(value=month, label=month.capitalize()) for month in MONTHS
]

# Day of week options
DAY_OF_WEEK_OPTIONS = [
    SelectOptionDict(value="0", label="Monday"),
    SelectOptionDict(value="1", label="Tuesday"),
    SelectOptionDict(value="2", label="Wednesday"),
    SelectOptionDict(value="3", label="Thursday"),
    SelectOptionDict(value="4", label="Friday"),
    SelectOptionDict(value="5", label="Saturday"),
    SelectOptionDict(value="6", label="Sunday"),
]


def get_month_selector(default: str) -> SelectSelector:
    """Get a month selector with proper labels."""
    return SelectSelector(
        SelectSelectorConfig(
            options=MONTH_OPTIONS,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def get_schedule_type_selector(default: str) -> SelectSelector:
    """Get a schedule type selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=SCHEDULE_TYPE_OPTIONS,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def get_day_of_week_selector(default: str) -> SelectSelector:
    """Get a day of week selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=DAY_OF_WEEK_OPTIONS,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def get_data_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Get the data schema with all possible fields."""
    # Include all fields, use Optional for conditional ones
    schema_dict = {
        vol.Required("name", default="My Schedule"): str,
        vol.Required("start_month", default="january"): get_month_selector("january"),
        vol.Required("end_month", default="december"): get_month_selector("december"),
        vol.Required("schedule_type", default="date"): get_schedule_type_selector("date"),
        vol.Optional("start_day", default=1): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=31,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Optional("end_day", default=31): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=31,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Optional("start_day_of_week", default="0"): get_day_of_week_selector("0"),
        vol.Optional("end_day_of_week", default="6"): get_day_of_week_selector("6"),
        vol.Optional("start_week", default=0): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=4,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Optional("end_week", default=4): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=4,
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
    
    return vol.Schema(schema_dict)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""
    start_month_idx = MONTHS.index(data["start_month"])
    end_month_idx = MONTHS.index(data["end_month"])

    if start_month_idx > end_month_idx:
        raise ValueError("Start month must be before or equal to end month")
    
    # Validate schedule type specific fields
    schedule_type = data.get("schedule_type", "date")
    
    if schedule_type == "date":
        start_day = data.get("start_day")
        end_day = data.get("end_day")
        
        if start_day is None:
            raise ValueError("Start day must be provided")
        if end_day is None:
            raise ValueError("End day must be provided")
            
        # Convert to int if it's a float (from NumberSelector)
        if isinstance(start_day, float):
            start_day = int(start_day)
            data["start_day"] = start_day
        if isinstance(end_day, float):
            end_day = int(end_day)
            data["end_day"] = end_day
            
        if not isinstance(start_day, int) or not isinstance(end_day, int):
            raise ValueError("Days must be numbers")
        if not 1 <= start_day <= 31:
            raise ValueError("Start day must be between 1 and 31")
        if not 1 <= end_day <= 31:
            raise ValueError("End day must be between 1 and 31")
        if start_day > end_day:
            raise ValueError("Start day must be before or equal to end day")
            
        # Remove week-based fields
        data.pop("start_day_of_week", None)
        data.pop("end_day_of_week", None)
        data.pop("start_week", None)
        data.pop("end_week", None)
    else:  # week
        start_day_of_week = data.get("start_day_of_week")
        end_day_of_week = data.get("end_day_of_week")
        start_week = data.get("start_week")
        end_week = data.get("end_week")
        
        if start_day_of_week is None:
            raise ValueError("Start day of week must be provided")
        if end_day_of_week is None:
            raise ValueError("End day of week must be provided")
        if start_week is None:
            raise ValueError("Start week must be provided")
        if end_week is None:
            raise ValueError("End week must be provided")
        
        # Convert to int if needed
        if isinstance(start_week, float):
            start_week = int(start_week)
            data["start_week"] = start_week
        if isinstance(end_week, float):
            end_week = int(end_week)
            data["end_week"] = end_week
        
        # Validate day_of_week values
        try:
            start_day_val = int(start_day_of_week)
            end_day_val = int(end_day_of_week)
            if not 0 <= start_day_val <= 6:
                raise ValueError("Start day of week must be between 0 and 6")
            if not 0 <= end_day_val <= 6:
                raise ValueError("End day of week must be between 0 and 6")
        except (ValueError, TypeError) as err:
            raise ValueError("Invalid day of week") from err
        
        # Validate week numbers
        if not isinstance(start_week, int) or not isinstance(end_week, int):
            raise ValueError("Week numbers must be integers")
        if not 0 <= start_week <= 4:
            raise ValueError("Start week must be between 0 and 4")
        if not 0 <= end_week <= 4:
            raise ValueError("End week must be between 0 and 4")
        if start_week > end_week:
            raise ValueError("Start week must be before or equal to end week")
            
        # Remove date-based fields
        data.pop("start_day", None)
        data.pop("end_day", None)

    return {"title": data["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Scheduler."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - name and type selection."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._data.update(user_input)
            # Route to the appropriate step based on schedule type
            if user_input["schedule_type"] == "date":
                return await self.async_step_date_config()
            else:
                return await self.async_step_week_config()

        schema = vol.Schema({
            vol.Required("name", default="My Schedule"): str,
            vol.Required("schedule_type", default="date"): get_schedule_type_selector("date"),
        })

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_date_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle date-based schedule configuration."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._data.update(user_input)
            try:
                info = await validate_input(self.hass, self._data)
            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                error_msg = str(err).lower()
                if "month" in error_msg and "day" not in error_msg:
                    errors["base"] = "invalid_month_range"
                elif "day" in error_msg:
                    errors["base"] = "invalid_day_range"
                else:
                    errors["base"] = "invalid_input"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=self._data)

        schema = vol.Schema({
            vol.Required("start_month", default="january"): get_month_selector("january"),
            vol.Required("end_month", default="december"): get_month_selector("december"),
            vol.Required("start_day", default=1): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=31,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required("end_day", default=31): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=31,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        })

        return self.async_show_form(
            step_id="date_config", data_schema=schema, errors=errors
        )

    async def async_step_week_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle week-based schedule configuration."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._data.update(user_input)
            try:
                info = await validate_input(self.hass, self._data)
            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                error_msg = str(err).lower()
                if "month" in error_msg and "day" not in error_msg:
                    errors["base"] = "invalid_month_range"
                elif "day of week" in error_msg:
                    errors["base"] = "invalid_day_of_week"
                elif "week" in error_msg:
                    errors["base"] = "invalid_week_range"
                else:
                    errors["base"] = "invalid_input"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=self._data)

        schema = vol.Schema({
            vol.Required("start_month", default="january"): get_month_selector("january"),
            vol.Required("end_month", default="december"): get_month_selector("december"),
            vol.Required("start_day_of_week", default="0"): get_day_of_week_selector("0"),
            vol.Required("end_day_of_week", default="6"): get_day_of_week_selector("6"),
            vol.Required("start_week", default=0): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=4,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required("end_week", default=4): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=4,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        })

        return self.async_show_form(
            step_id="week_config", data_schema=schema, errors=errors
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
        """Initialize the options flow."""
        self._data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - name and type selection."""
        errors: dict[str, str] = {}
        
        # Pre-fill with current values
        current_data = self.config_entry.data
        
        if user_input is not None:
            self._data.update(user_input)
            # Route to the appropriate step based on schedule type
            if user_input["schedule_type"] == "date":
                return await self.async_step_date_config()
            else:
                return await self.async_step_week_config()

        schema = vol.Schema({
            vol.Required("name", default=current_data.get("name", "My Schedule")): str,
            vol.Required("schedule_type", default=current_data.get("schedule_type", "date")): get_schedule_type_selector(current_data.get("schedule_type", "date")),
        })

        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )

    async def async_step_date_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle date-based schedule configuration."""
        errors: dict[str, str] = {}
        current_data = self.config_entry.data
        
        if user_input is not None:
            self._data.update(user_input)
            try:
                info = await validate_input(self.hass, self._data)
            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                error_msg = str(err).lower()
                if "month" in error_msg and "day" not in error_msg:
                    errors["base"] = "invalid_month_range"
                elif "day" in error_msg:
                    errors["base"] = "invalid_day_range"
                else:
                    errors["base"] = "invalid_input"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Update config entry data
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=self._data,
                    title=self._data["name"],
                )
                return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Required("start_month", default=current_data.get("start_month", "january")): get_month_selector(current_data.get("start_month", "january")),
            vol.Required("end_month", default=current_data.get("end_month", "december")): get_month_selector(current_data.get("end_month", "december")),
            vol.Required("start_day", default=current_data.get("start_day", 1)): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=31,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required("end_day", default=current_data.get("end_day", 31)): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=31,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        })

        return self.async_show_form(
            step_id="date_config", data_schema=schema, errors=errors
        )

    async def async_step_week_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle week-based schedule configuration."""
        errors: dict[str, str] = {}
        current_data = self.config_entry.data
        
        if user_input is not None:
            self._data.update(user_input)
            try:
                info = await validate_input(self.hass, self._data)
            except ValueError as err:
                _LOGGER.warning("Validation error: %s", err)
                error_msg = str(err).lower()
                if "month" in error_msg and "day" not in error_msg:
                    errors["base"] = "invalid_month_range"
                elif "day of week" in error_msg:
                    errors["base"] = "invalid_day_of_week"
                elif "week" in error_msg:
                    errors["base"] = "invalid_week_range"
                else:
                    errors["base"] = "invalid_input"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Update config entry data
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=self._data,
                    title=self._data["name"],
                )
                return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Required("start_month", default=current_data.get("start_month", "january")): get_month_selector(current_data.get("start_month", "january")),
            vol.Required("end_month", default=current_data.get("end_month", "december")): get_month_selector(current_data.get("end_month", "december")),
            vol.Required("start_day_of_week", default=current_data.get("start_day_of_week", "0")): get_day_of_week_selector(current_data.get("start_day_of_week", "0")),
            vol.Required("end_day_of_week", default=current_data.get("end_day_of_week", "6")): get_day_of_week_selector(current_data.get("end_day_of_week", "6")),
            vol.Required("start_week", default=current_data.get("start_week", 0)): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=4,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required("end_week", default=current_data.get("end_week", 4)): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=4,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        })

        return self.async_show_form(
            step_id="week_config", data_schema=schema, errors=errors
        )
