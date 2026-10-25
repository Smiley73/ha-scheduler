"""Config flow for Scheduler integration."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from functools import partial
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
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.util import dt as dt_util

from . import holiday_importer, schedule_generator
from .const import (
    DAY_NAMES,
    DOMAIN,
    OCCURRENCE_NAMES,
    SCHEDULE_TYPE_DATE,
    SCHEDULE_TYPE_HOLIDAY,
    SCHEDULE_TYPE_NTH_DAY,
    SCHEDULE_TYPE_WEEK,
    WEEK_OCCURRENCE_OPTIONS,
)
from .migrations import backfill_schedule_uids

_LOGGER = logging.getLogger(__name__)

_SERVICE_ID = "default"


def _form_schema(schema: dict[Any, Any]) -> Any:
    """Build a form schema for ``async_show_form``.

    Typed ``Any`` on purpose: Home Assistant 2026.10 annotates ``data_schema``
    as ``probatio.Schema`` (accepting voluptuous schemas through its shim),
    while the supported floor (2024.12) only knows voluptuous. A single
    boundary keeps mypy green on both without per-call ignores.
    """
    return vol.Schema(schema)


def _month_selector() -> SelectSelector:
    """Month dropdown (values are integers 1-12, labels via translations)."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[str(i) for i in range(1, 13)],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="month",
        )
    )


def _offset_selector() -> NumberSelector:
    """Day offset input (0-30)."""
    return NumberSelector(
        NumberSelectorConfig(min=0, max=30, mode=NumberSelectorMode.BOX)
    )


def _week_occurrence_selector() -> SelectSelector:
    """Week occurrence dropdown (labels via the week_occurrence translations)."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[value for value, _label in WEEK_OCCURRENCE_OPTIONS],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="week_occurrence",
        )
    )


def _week_day_selector() -> SelectSelector:
    """Day-of-week dropdown with a "Whole week" choice (values are 0-6)."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value="", label="Whole week"),
                *(
                    SelectOptionDict(value=str(i), label=DAY_NAMES[i].capitalize())
                    for i in range(7)
                ),
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _configuration_field(default: str = "") -> dict[vol.Marker, Any]:
    """Multiline YAML ``configuration`` form field."""
    return {
        vol.Optional("configuration", default=default): TextSelector(
            TextSelectorConfig(multiline=True)
        )
    }


def _schedule_picker_schema(schedules: dict[str, Any]) -> Any:
    """Schema for picking one schedule, sorted by name."""
    schedule_options = [
        SelectOptionDict(value=sid, label=sdata["name"])
        for sid, sdata in sorted(schedules.items(), key=lambda x: x[1]["name"].lower())
    ]
    return _form_schema(
        {
            vol.Required("schedule_id"): SelectSelector(
                SelectSelectorConfig(
                    options=schedule_options, mode=SelectSelectorMode.DROPDOWN
                )
            ),
        }
    )


def _parse_week_value(value: str) -> tuple[int, str]:
    """Split a combined ``"N"`` / ``"0_type"`` value into week and week type."""
    week, separator, week_type = value.partition("_")
    return int(week), week_type if separator else "partial"


def _format_week_value(week: int | str, week_type: str) -> str:
    """Inverse of ``_parse_week_value`` for form defaults."""
    return f"{week}_{week_type}" if week == 0 else str(week)


def _get_schedule_type_display(schedule_type: str) -> str:
    """Return a display label for a schedule type."""
    display_names = {
        SCHEDULE_TYPE_DATE: "By Date",
        SCHEDULE_TYPE_WEEK: "By Week of Month",
        SCHEDULE_TYPE_NTH_DAY: "By Nth Day of Month",
        SCHEDULE_TYPE_HOLIDAY: "By Holiday",
    }
    return display_names.get(schedule_type, schedule_type)


def _validate_yaml_config(yaml_str: str) -> dict[str, Any] | list[Any]:
    """Validate YAML configuration string.

    Returns the parsed structure (dict or list) if valid and raises
    ``ValueError`` if invalid.
    """
    try:
        parsed = yaml.safe_load(yaml_str)
        if not isinstance(parsed, (dict, list)):
            raise ValueError(
                "Configuration must be a YAML structure (dict or list), "
                "not a simple value"
            )
        return parsed
    except yaml.YAMLError as err:
        raise ValueError(f"Invalid YAML: {err}") from err


def _parse_optional_yaml(value: Any) -> dict[str, Any] | list[Any] | None:
    """Parse a submitted ``configuration`` value; ``None`` when blank."""
    text = value.strip() if isinstance(value, str) else ""
    return _validate_yaml_config(text) if text else None


def _get_holiday_options(
    holidays_data: dict[str, dict[str, Any]],
) -> list[SelectOptionDict]:
    """Build holiday selector options with pattern descriptions when available."""
    holiday_options: list[SelectOptionDict] = []

    for holiday_name, holiday_info in sorted(
        holidays_data.items(), key=lambda item: item[0].lower()
    ):
        if holiday_info is None:
            _LOGGER.warning("Holiday info is None for %s", holiday_name)
            continue

        pattern = holiday_info.get("pattern")
        description = (
            pattern.get("description", "Unknown pattern")
            if pattern is not None
            else "No pattern available"
        )
        holiday_options.append(
            SelectOptionDict(
                value=holiday_name, label=f"{holiday_name} ({description})"
            )
        )

    return holiday_options


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
            data_schema=_form_schema(
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
        self._schedule_id: str | None = None
        self._schedule_data: dict[str, Any] = {}
        self._holiday_data: dict[str, Any] = {}
        self._overlap_conflicting_name = ""
        self._yaml_error_details = ""

    def _get_service_schedules(self) -> dict[str, Any]:
        """Get schedules for the current service."""
        schedules = (
            self.config_entry.options.get("services", {})
            .get(_SERVICE_ID, {})
            .get("schedules", {})
        )
        return backfill_schedule_uids(schedules)

    def _get_default_holiday_country(self) -> str | None:
        """Return the default country for holiday schedules."""
        if country_code := self._schedule_data.get("country_code"):
            return str(country_code)

        country = self.hass.config.country
        return str(country) if country else None

    def _set_service_field(self, field: str, value: Any) -> dict[str, Any]:
        """Return the entry options with one field of the service replaced."""
        entry = self.config_entry
        services = dict(entry.options.get("services", {}))
        service = services.get(
            _SERVICE_ID, {"name": entry.title, "schedules": {}, "configuration": {}}
        )
        services[_SERVICE_ID] = {**service, field: value}
        return {**entry.options, "services": services}

    def _save_schedule(
        self, schedule_id: str, schedule: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge one schedule into freshly-read options and return them.

        Re-reading at write time (with no awaits before the write) keeps a
        concurrently-finished flow's save from being clobbered: validation
        runs on a snapshot, but only this schedule key is written.
        """
        schedules = self._get_service_schedules()
        schedules[schedule_id] = schedule
        return self._set_service_field("schedules", schedules)

    def _remove_schedule(self, schedule_id: str) -> dict[str, Any]:
        """Remove one schedule from freshly-read options and return them."""
        schedules = self._get_service_schedules()
        schedules.pop(schedule_id, None)
        return self._set_service_field("schedules", schedules)

    def _error_placeholders(self, errors: dict[str, str]) -> dict[str, str] | None:
        """Return description placeholders for the current error state."""
        if errors.get("base") == "schedule_overlap_with_name":
            return {"conflicting_schedule": self._overlap_conflicting_name}
        if errors.get("base") == "invalid_yaml_with_details":
            return {"details": self._yaml_error_details}
        return None

    def _set_submit_error(self, err: Exception, errors: dict[str, str]) -> None:
        """Map an exception raised while handling a submit to a form error."""
        if isinstance(err, ValueError):
            _LOGGER.warning("Validation error: %s", err)
            self._yaml_error_details = str(err).strip()
            errors["base"] = (
                "invalid_yaml_with_details"
                if self._yaml_error_details
                else "invalid_yaml"
            )
        else:
            _LOGGER.exception("Unexpected error")
            errors["base"] = "unknown"

    def _form_defaults(
        self, user_input: dict[str, Any] | None, errors: dict[str, str]
    ) -> tuple[dict[str, Any], str]:
        """Return form defaults and the YAML text for the configuration field.

        After an error the user's own input is redisplayed; otherwise the
        stored schedule data is.
        """
        defaults = user_input if user_input and errors else self._schedule_data
        config_value = defaults.get("configuration", "")
        if isinstance(config_value, (dict, list)):
            config_value = yaml.dump(
                config_value, default_flow_style=False, sort_keys=False
            ).strip()
        return defaults, config_value

    def _show_configure_form(
        self,
        step_id: str,
        fields: dict[vol.Marker, Any],
        config_value: str,
        errors: dict[str, str],
    ) -> ConfigFlowResult:
        """Show a form of ``fields`` followed by the configuration field."""
        return self.async_show_form(
            step_id=step_id,
            data_schema=_form_schema({**fields, **_configuration_field(config_value)}),
            errors=errors,
            description_placeholders=self._error_placeholders(errors),
        )

    async def _check_overlap(
        self,
        schedule: dict[str, Any],
        existing: list[dict[str, Any]],
        exclude_uid: str | None,
    ) -> tuple[bool, str | None]:
        """Prime the holiday cache, then run the overlap check in the executor."""
        current_year = dt_util.now().date().year
        await holiday_importer.async_prime_holiday_cache(
            [schedule, *existing],
            range(
                current_year,
                current_year + schedule_generator.HOLIDAY_OVERLAP_HORIZON + 1,
            ),
        )
        # Overlap validation generates schedules across a 400-year cycle;
        # run it in the executor to keep the event loop responsive.
        return await self.hass.async_add_executor_job(
            partial(
                schedule_generator.check_overlap,
                schedule,
                existing,
                exclude_uid=exclude_uid,
                today=dt_util.now().date(),
            )
        )

    async def _validate_schedule_conflicts(
        self, data: dict[str, Any], schedules: dict[str, Any]
    ) -> dict[str, str]:
        """Check for duplicate names and date overlaps against existing schedules.

        Returns an errors dict (empty when there are no conflicts).
        """
        schedule_name = data["name"].strip().lower()
        for sid, schedule in schedules.items():
            if (
                sid != self._schedule_id
                and schedule["name"].strip().lower() == schedule_name
            ):
                return {"name": "duplicate_name"}

        has_overlap, conflicting_name = await self._check_overlap(
            data,
            list(schedules.values()),
            # When editing, exclude the current schedule so it doesn't conflict with itself.
            # When adding, _schedule_id is a new UUID not yet in schedules, so exclude_uid=None.
            self._schedule_id if self._schedule_id in schedules else None,
        )
        if not has_overlap:
            return {}

        _LOGGER.debug("Schedule overlaps with existing schedule: %s", conflicting_name)
        self._overlap_conflicting_name = conflicting_name or ""
        return {
            "base": "schedule_overlap_with_name"
            if conflicting_name
            else "schedule_overlap"
        }

    async def _validate_week_schedule(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate that a week schedule produces a valid recurring range.

        Runs in the executor: validation generates ranges across a 400-year
        cycle and may load Babel locale data from disk on first use.
        """
        if data.get("schedule_type") != SCHEDULE_TYPE_WEEK:
            return {}

        if await self.hass.async_add_executor_job(
            schedule_generator.week_schedule_has_valid_ranges, data
        ):
            return {}

        return {"base": "invalid_week_schedule"}

    async def _submit_schedule(
        self,
        user_input: dict[str, Any],
        errors: dict[str, str],
        build: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> ConfigFlowResult | None:
        """Build, validate and save the schedule submitted from a configure step.

        Returns the flow result once the schedule is saved (or the flow aborts).
        Returns ``None`` with ``errors`` filled in when the form should be shown
        again.
        """
        try:
            data = build(user_input)
            config = _parse_optional_yaml(user_input.get("configuration"))
            if config is not None:
                data["configuration"] = config

            errors.update(await self._validate_week_schedule(data))
            if not errors:
                errors.update(
                    await self._validate_schedule_conflicts(
                        data, self._get_service_schedules()
                    )
                )

            if not errors:
                schedule_id = self._schedule_id
                if schedule_id is None:
                    return self.async_abort(reason="unknown")
                return self.async_create_entry(
                    title="", data=self._save_schedule(schedule_id, data)
                )
        except Exception as err:  # noqa: BLE001 - surfaced as the form's unknown error
            self._set_submit_error(err, errors)
        return None

    async def _configure_schedule_type(self, schedule_type: str) -> ConfigFlowResult:
        """Continue to the first configure step for ``schedule_type``."""
        if schedule_type == SCHEDULE_TYPE_DATE:
            return await self.async_step_configure_date()
        if schedule_type == SCHEDULE_TYPE_WEEK:
            return await self.async_step_configure_week()
        if schedule_type == SCHEDULE_TYPE_HOLIDAY:
            return await self.async_step_configure_holiday_country()
        return await self.async_step_configure_nth_day()

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
            return await self._configure_schedule_type(user_input["schedule_type"])

        return self.async_show_form(
            step_id="add_schedule",
            data_schema=_form_schema(
                {
                    vol.Required(
                        "schedule_type", default=SCHEDULE_TYPE_DATE
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SCHEDULE_TYPE_DATE,
                                SCHEDULE_TYPE_WEEK,
                                SCHEDULE_TYPE_NTH_DAY,
                                SCHEDULE_TYPE_HOLIDAY,
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="schedule_type",
                        )
                    ),
                }
            ),
        )

    def _build_date(self, user_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": user_input["name"],
            "schedule_type": SCHEDULE_TYPE_DATE,
            "start_month": int(user_input["start_month"]),
            "start_day": int(user_input["start_day"]),
            "end_month": int(user_input["end_month"]),
            "end_day": int(user_input["end_day"]),
            "uid": self._schedule_id,
        }

    async def async_step_configure_date(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure date-based schedule (single page)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if result := await self._submit_schedule(
                user_input, errors, self._build_date
            ):
                return result

        defaults, config_value = self._form_defaults(user_input, errors)
        return self._show_configure_form(
            "configure_date",
            {
                vol.Required("name", default=defaults.get("name", "My Schedule")): str,
                vol.Required(
                    "start_month", default=str(defaults.get("start_month", 1))
                ): _month_selector(),
                vol.Required(
                    "start_day", default=defaults.get("start_day", 1)
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=31, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(
                    "end_month", default=str(defaults.get("end_month", 12))
                ): _month_selector(),
                vol.Required(
                    "end_day", default=defaults.get("end_day", 31)
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=31, mode=NumberSelectorMode.BOX)
                ),
            },
            config_value,
            errors,
        )

    def _build_week(self, user_input: dict[str, Any]) -> dict[str, Any]:
        start_week, start_week_type = _parse_week_value(user_input["start_week"])
        end_week, end_week_type = _parse_week_value(user_input["end_week"])

        data: dict[str, Any] = {
            "name": user_input["name"],
            "schedule_type": SCHEDULE_TYPE_WEEK,
            "start_month": int(user_input["start_month"]),
            "start_week": start_week,
            "end_month": int(user_input["end_month"]),
            "end_week": end_week,
            "uid": self._schedule_id,
        }

        # The week type only applies to the first week (occurrence 0)
        if start_week == 0:
            data["start_week_type"] = start_week_type
        if end_week == 0:
            data["end_week_type"] = end_week_type

        for key in ("start_day_of_week", "end_day_of_week"):
            if user_input.get(key):
                data[key] = int(user_input[key])

        # Preserve the stored country when editing: silently adopting
        # the current Home Assistant country would shift week
        # boundaries (Monday-first vs Sunday-first) on unrelated
        # edits. Only new schedules take the HA country.
        if stored_country := self._schedule_data.get("country_code"):
            data["country_code"] = stored_country
        elif country := self.hass.config.country:
            data["country_code"] = country
        else:
            _LOGGER.debug(
                "No country configured in Home Assistant; week "
                "schedules default to Monday-first weeks"
            )
        return data

    async def async_step_configure_week(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure week-based schedule (single page)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if result := await self._submit_schedule(
                user_input, errors, self._build_week
            ):
                return result

        defaults, config_value = self._form_defaults(user_input, errors)
        return self._show_configure_form(
            "configure_week",
            {
                vol.Required("name", default=defaults.get("name", "My Schedule")): str,
                vol.Required(
                    "start_month", default=str(defaults.get("start_month", 1))
                ): _month_selector(),
                vol.Required(
                    "start_week",
                    default=_format_week_value(
                        defaults.get("start_week", 0),
                        defaults.get("start_week_type", "partial"),
                    ),
                ): _week_occurrence_selector(),
                vol.Optional(
                    "start_day_of_week",
                    default=str(defaults.get("start_day_of_week", "")),
                ): _week_day_selector(),
                vol.Required(
                    "end_month", default=str(defaults.get("end_month", 12))
                ): _month_selector(),
                vol.Required(
                    "end_week",
                    default=_format_week_value(
                        defaults.get("end_week", 4),
                        defaults.get("end_week_type", "partial"),
                    ),
                ): _week_occurrence_selector(),
                vol.Optional(
                    "end_day_of_week", default=str(defaults.get("end_day_of_week", ""))
                ): _week_day_selector(),
            },
            config_value,
            errors,
        )

    def _build_nth_day(self, user_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": user_input["name"],
            "schedule_type": SCHEDULE_TYPE_NTH_DAY,
            "month": int(user_input["month"]),
            "occurrence": int(user_input["occurrence"]),
            "day_of_week": int(user_input["day_of_week"]),
            "start_offset": int(user_input["start_offset"]),
            "end_offset": int(user_input["end_offset"]),
            "uid": self._schedule_id,
        }

    async def async_step_configure_nth_day(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure nth-day schedule (single page)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if result := await self._submit_schedule(
                user_input, errors, self._build_nth_day
            ):
                return result

        defaults, config_value = self._form_defaults(user_input, errors)
        return self._show_configure_form(
            "configure_nth_day",
            {
                vol.Required("name", default=defaults.get("name", "My Schedule")): str,
                vol.Required(
                    "month", default=str(defaults.get("month", 1))
                ): _month_selector(),
                vol.Required(
                    "occurrence", default=str(defaults.get("occurrence", 0))
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[str(i) for i in range(len(OCCURRENCE_NAMES))],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="occurrence",
                    )
                ),
                vol.Required(
                    "day_of_week", default=str(defaults.get("day_of_week", 0))
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[str(i) for i in range(7)],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="day_of_week",
                    )
                ),
                vol.Required(
                    "start_offset", default=defaults.get("start_offset", 0)
                ): _offset_selector(),
                vol.Required(
                    "end_offset", default=defaults.get("end_offset", 0)
                ): _offset_selector(),
            },
            config_value,
            errors,
        )

    async def async_step_configure_holiday_country(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the country for a holiday-backed schedule."""
        if user_input is not None:
            selected_country = user_input["country_code"]
            if self._schedule_data.get("country_code") != selected_country:
                self._schedule_data.pop("category", None)
                self._schedule_data.pop("holiday_name", None)
            self._schedule_data["country_code"] = selected_country
            return await self.async_step_configure_holiday_category()

        try:
            countries = await holiday_importer.get_supported_countries(
                today=dt_util.now().date()
            )
        except Exception:
            _LOGGER.exception("Failed to load holiday countries")
            return self.async_abort(reason="import_error")

        if not countries:
            return self.async_abort(reason="no_countries_available")

        default_country = self._get_default_holiday_country()
        if default_country not in countries:
            default_country = next(iter(countries))

        country_options = [
            SelectOptionDict(value=code, label=name)
            for code, name in sorted(countries.items(), key=lambda item: item[1])
        ]

        return self.async_show_form(
            step_id="configure_holiday_country",
            data_schema=_form_schema(
                {
                    vol.Required(
                        "country_code", default=default_country
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=country_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_configure_holiday_category(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the holiday category for a holiday-backed schedule."""
        country_code = self._schedule_data.get("country_code")
        if not country_code:
            return await self.async_step_configure_holiday_country()

        if user_input is not None:
            selected_category = user_input["category"]
            if self._schedule_data.get("category") != selected_category:
                self._schedule_data.pop("holiday_name", None)
            self._schedule_data["category"] = selected_category
            return await self.async_step_configure_holiday()

        try:
            categories = await holiday_importer.get_available_categories(
                str(country_code), today=dt_util.now().date()
            )
        except Exception:
            _LOGGER.exception("Failed to load holiday categories for %s", country_code)
            return self.async_abort(reason="import_error")

        if not categories:
            categories = {"public": "Public Holidays"}

        default_category = str(self._schedule_data.get("category", "public"))
        if default_category not in categories:
            default_category = next(iter(categories))

        category_options = [
            SelectOptionDict(value=code, label=name)
            for code, name in sorted(categories.items(), key=lambda item: item[1])
        ]

        return self.async_show_form(
            step_id="configure_holiday_category",
            data_schema=_form_schema(
                {
                    vol.Required("category", default=default_category): SelectSelector(
                        SelectSelectorConfig(
                            options=category_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_configure_holiday(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a holiday-backed schedule."""
        errors: dict[str, str] = {}

        country_code = self._schedule_data.get("country_code")
        category = self._schedule_data.get("category")
        if not country_code:
            return await self.async_step_configure_holiday_country()
        if not category:
            return await self.async_step_configure_holiday_category()

        holidays_data: dict[str, dict[str, Any]] = {}
        try:
            holidays_data = await holiday_importer.get_holidays_for_country(
                str(country_code), [category], today=dt_util.now().date()
            )
        except Exception:
            _LOGGER.exception(
                "Failed to load holidays for %s/%s", country_code, category
            )
            errors["base"] = "import_error"

        holiday_options = _get_holiday_options(holidays_data)

        if user_input is not None:

            def build(form: dict[str, Any]) -> dict[str, Any]:
                holiday_name = form["holiday_name"]
                if holiday_name not in holidays_data:
                    errors["holiday_name"] = "invalid_holiday_selection"
                return {
                    "name": form["name"],
                    "schedule_type": SCHEDULE_TYPE_HOLIDAY,
                    "country_code": str(country_code),
                    "category": str(category),
                    "holiday_name": holiday_name,
                    "name_lookup": "iexact",
                    "start_offset": int(form["start_offset"]),
                    "end_offset": int(form["end_offset"]),
                    "uid": self._schedule_id,
                }

            if result := await self._submit_schedule(user_input, errors, build):
                return result

        if not holiday_options and "base" not in errors:
            errors["base"] = "no_holidays_available"

        defaults, config_value = self._form_defaults(user_input, errors)

        available_holiday_names = {option["value"] for option in holiday_options}
        default_holiday_name = defaults.get("holiday_name")
        if default_holiday_name not in available_holiday_names:
            # Surface a warning instead of silently preselecting a different
            # holiday: the stored name may have been renamed or removed by
            # the installed holidays library.
            if user_input is None and default_holiday_name and holiday_options:
                errors.setdefault("holiday_name", "stored_holiday_not_found")
            default_holiday_name = (
                holiday_options[0]["value"] if holiday_options else ""
            )

        return self._show_configure_form(
            "configure_holiday",
            {
                vol.Required(
                    "name", default=defaults.get("name", "My Holiday Schedule")
                ): str,
                vol.Required(
                    "holiday_name", default=default_holiday_name
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=holiday_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    "start_offset", default=defaults.get("start_offset", 0)
                ): _offset_selector(),
                vol.Required(
                    "end_offset", default=defaults.get("end_offset", 0)
                ): _offset_selector(),
            },
            config_value,
            errors,
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
            return await self._configure_schedule_type(schedule["schedule_type"])

        return self.async_show_form(
            step_id="edit_schedule", data_schema=_schedule_picker_schema(schedules)
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
                data_schema=_form_schema(
                    {
                        vol.Required("confirm", default=False): bool,
                    }
                ),
                description_placeholders={
                    "schedule_name": schedule["name"],
                    "schedule_type": _get_schedule_type_display(
                        schedule["schedule_type"]
                    ),
                },
            )

        return self.async_show_form(
            step_id="remove_schedule", data_schema=_schedule_picker_schema(schedules)
        )

    async def async_step_remove_schedule_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm schedule removal."""
        if user_input is not None:
            if user_input.get("confirm"):
                schedule_id = self._schedule_id
                if schedule_id is None:
                    return self.async_abort(reason="unknown")
                updated_options = self._remove_schedule(schedule_id)

                return self.async_create_entry(title="", data=updated_options)

            return self.async_abort(reason="not_confirmed")

        # This should not happen as we redirect here from remove_schedule
        return self.async_abort(reason="unknown")

    async def async_step_default_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure default configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                config_dict = _parse_optional_yaml(user_input.get("configuration"))
                return self.async_create_entry(
                    title="",
                    data=self._set_service_field(
                        "configuration", {} if config_dict is None else config_dict
                    ),
                )
            except UnknownEntry:
                errors["base"] = "entry_not_found"
                return self._show_configure_form(
                    "default_configuration", {}, "", errors
                )
            except Exception as err:  # noqa: BLE001 - surfaced as the form's unknown error
                self._set_submit_error(err, errors)

        if user_input is not None and errors:
            # Preserve what the user typed so they can correct it
            config_str = user_input.get("configuration") or ""
        else:
            current_config = (
                self.config_entry.options.get("services", {})
                .get(_SERVICE_ID, {})
                .get("configuration", {})
            )
            config_str = yaml.dump(current_config) if current_config else ""

        return self._show_configure_form(
            "default_configuration", {}, config_str, errors
        )

    async def async_step_import_holidays(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import holidays - step 1: select country."""
        if user_input is not None:
            self._holiday_data = {"country": user_input["country"]}
            return await self.async_step_import_holidays_categories()

        try:
            countries = await holiday_importer.get_supported_countries(
                today=dt_util.now().date()
            )

            if not countries:
                return self.async_abort(reason="no_countries_available")

            country_options = [
                SelectOptionDict(value=code, label=name)
                for code, name in sorted(countries.items(), key=lambda x: x[1])
            ]

            return self.async_show_form(
                step_id="import_holidays",
                data_schema=_form_schema(
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
        except Exception:
            _LOGGER.exception("Failed to load countries")
            return self.async_abort(reason="import_error")

    async def async_step_import_holidays_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import holidays - step 2: select categories."""
        if user_input is not None:
            self._holiday_data["categories"] = user_input.get("categories", ["public"])
            return await self.async_step_import_holidays_select()

        try:
            country = self._holiday_data.get("country")
            if not country:
                return self.async_abort(reason="import_error")
            categories = await holiday_importer.get_available_categories(
                country, today=dt_util.now().date()
            )

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
                data_schema=_form_schema(
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
        except Exception:
            _LOGGER.exception("Failed to load categories")
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
            use_holiday_type = user_input.get("use_holiday_type", True)

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
                use_holiday_type,
            )

        return self.async_show_form(
            step_id="import_holidays_select",
            data_schema=await self._get_holiday_selection_schema(),
        )

    async def _get_holiday_selection_schema(self) -> Any:
        """Get the schema for holiday selection."""
        empty_schema = _form_schema(
            {
                vol.Optional("holidays", default=[]): SelectSelector(
                    SelectSelectorConfig(options=[], multiple=True)
                ),
            }
        )

        try:
            country = self._holiday_data.get("country")
            categories = self._holiday_data.get("categories", ["public"])

            if not country:
                return empty_schema

            holidays_data = await holiday_importer.get_holidays_for_country(
                country, categories, today=dt_util.now().date()
            )

            _LOGGER.debug(
                "Got %d holidays for country %s, categories %s",
                len(holidays_data) if holidays_data else 0,
                country,
                categories,
            )

            if not holidays_data:
                return empty_schema

            holiday_options = _get_holiday_options(holidays_data)
            all_holiday_names = [option["value"] for option in holiday_options]

            return _form_schema(
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
                    vol.Optional("use_holiday_type", default=True): bool,
                }
            )

        except Exception:
            _LOGGER.exception("Failed to get holidays")
            return empty_schema

    async def _import_selected_holidays(
        self,
        selected_holidays: list[str],
        overwrite_existing: bool,
        skip_on_overlap: bool,
        include_country_name: bool = False,
        use_holiday_type: bool = True,
    ) -> ConfigFlowResult:
        """Import the selected holidays as schedules."""
        try:
            country = self._holiday_data.get("country")
            categories = self._holiday_data.get("categories", ["public"])

            if not country:
                return self.async_abort(reason="import_error")

            all_holidays = await holiday_importer.get_holidays_for_country(
                country, categories, today=dt_util.now().date()
            )

            schedules = self._get_service_schedules()
            new_schedules = dict(schedules)
            # Only the schedules this import adds or overwrites; merged into
            # freshly-read options at write time so a concurrent flow's save
            # isn't clobbered by this snapshot.
            changed_schedules: dict[str, Any] = {}

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

                if use_holiday_type:
                    holiday_category = str(
                        holiday_info.get("category")
                        or (categories[0] if categories else "public")
                    )
                    pattern = holiday_importer.build_holiday_schedule_pattern(
                        str(country), holiday_category, holiday_name
                    )

                if not pattern:
                    errors.append(f"Could not determine pattern for '{holiday_name}'")
                    continue

                if include_country_name:
                    schedule_name = f"{holiday_name} ({country})"
                else:
                    schedule_name = holiday_name
                schedule_name = schedule_name.strip()
                normalized_schedule_name = schedule_name.lower()
                schedule = {
                    "uid": str(uuid.uuid4()),
                    "name": schedule_name,
                    # description/variable_date are analysis metadata, not
                    # schedule fields.
                    **{
                        k: v
                        for k, v in pattern.items()
                        if k not in ("description", "variable_date")
                    },
                }

                existing_schedule_id = None
                for sid, existing_schedule in new_schedules.items():
                    if (
                        existing_schedule["name"].strip().lower()
                        == normalized_schedule_name
                    ):
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
                        skipped_count += 1
                        errors.append(
                            f"Schedule '{schedule_name}' already exists (skipped)"
                        )
                        continue

                has_overlap, conflicting_name = await self._check_overlap(
                    schedule, list(new_schedules.values()), excluded_uid
                )

                if has_overlap and skip_on_overlap:
                    skipped_count += 1
                    errors.append(
                        f"Holiday '{holiday_name}' overlaps with '{conflicting_name}' (skipped)"
                    )
                    continue

                if existing_schedule_id and overwrite_existing:
                    new_schedules[existing_schedule_id] = schedule
                    changed_schedules[existing_schedule_id] = schedule
                    overwritten_count += 1
                    continue

                # Add the schedule (importing despite overlap when skip_on_overlap is False)
                new_schedules[schedule["uid"]] = schedule
                changed_schedules[schedule["uid"]] = schedule
                imported_count += 1

            if imported_count > 0 or overwritten_count > 0:
                merged_schedules = self._get_service_schedules()
                merged_schedules.update(changed_schedules)
                updated_options = self._set_service_field("schedules", merged_schedules)

                _LOGGER.info(
                    "Holiday import for %s: %d imported, %d overwritten, %d skipped%s",
                    country,
                    imported_count,
                    overwritten_count,
                    skipped_count,
                    f" ({'; '.join(errors)})" if errors else "",
                )

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
