"""Config flow for Ford Assistant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ALARM_NORMAL_STATES,
    CONF_GARAGE,
    CONF_HOME_ZONE,
    CONF_NOTIFY_DEVICES,
    CONF_PHONE_TRACKER,
    CONF_PRECONDITION_DAYS,
    CONF_TODO,
    CONF_VIN,
    CONF_WEATHER,
    CONF_WORK_PROMPT_DAYS,
    CONF_WORK_ZONE,
    DEFAULT_ALARM_NORMAL_STATES,
    DEFAULT_DAYS,
    DOMAIN,
    WEEKDAYS,
)
from .discovery import ford_vehicles, resolve_entities
from .importer import BlueprintSettings, find_blueprint_automations

CONF_AUTOMATION = "automation"
CONF_DISABLE_AUTOMATION = "disable_automation"
SKIP_IMPORT = "skip"

DAY_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=WEEKDAYS,
        multiple=True,
        mode=selector.SelectSelectorMode.LIST,
        translation_key="weekday",
    )
)


def _settings_schema() -> vol.Schema:
    """Fields shared by setup and options."""
    return vol.Schema(
        {
            vol.Required(CONF_NOTIFY_DEVICES, default=[]): selector.DeviceSelector(
                selector.DeviceSelectorConfig(integration="mobile_app", multiple=True)
            ),
            vol.Optional(CONF_PHONE_TRACKER): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="device_tracker", integration="mobile_app"
                )
            ),
            vol.Required(CONF_HOME_ZONE, default="zone.home"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="zone")
            ),
            vol.Optional(CONF_WORK_ZONE): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="zone")
            ),
            vol.Optional(CONF_WEATHER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_TODO): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="todo")
            ),
            vol.Optional(CONF_GARAGE): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="cover", device_class="garage")
            ),
        }
    )


class FordAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick a Ford vehicle, then where to send alerts."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._vin: str | None = None
        self._blueprints: list[BlueprintSettings] = []
        self._import: BlueprintSettings | None = None
        self._disable_automation = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the vehicle."""
        configured = {e.unique_id for e in self._async_current_entries()}
        vehicles = {
            vin: name
            for vin, name in ford_vehicles(self.hass).items()
            if vin not in configured
        }
        if not vehicles:
            reason = "already_configured" if configured else "no_vehicles"
            return self.async_abort(reason=reason)

        errors: dict[str, str] = {}
        if user_input is not None:
            vin = user_input[CONF_VIN]
            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()
            entities = resolve_entities(self.hass, vin)
            if "lock" not in entities or "tracker" not in entities:
                errors["base"] = "missing_entities"
            else:
                self._vin = vin
                self._blueprints = find_blueprint_automations(
                    self.hass, entities.get("lock")
                )
                if self._blueprints:
                    return await self.async_step_import_blueprint()
                return await self.async_step_settings()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIN): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=vin, label=name)
                                for vin, name in vehicles.items()
                            ]
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_import_blueprint(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer to copy settings from an existing blueprint automation."""
        if user_input is not None:
            choice = user_input[CONF_AUTOMATION]
            self._import = next(
                (b for b in self._blueprints if b.entity_id == choice), None
            )
            self._disable_automation = bool(
                self._import and user_input.get(CONF_DISABLE_AUTOMATION)
            )
            return await self.async_step_settings()

        options = [
            selector.SelectOptionDict(value=b.entity_id, label=b.name)
            for b in self._blueprints
        ]
        options.append(selector.SelectOptionDict(value=SKIP_IMPORT, label=SKIP_IMPORT))
        return self.async_show_form(
            step_id="import_blueprint",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTOMATION, default=self._blueprints[0].entity_id
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, translation_key="import_choice"
                        )
                    ),
                    vol.Required(CONF_DISABLE_AUTOMATION, default=True): bool,
                }
            ),
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Where to send alerts and which places matter."""
        assert self._vin is not None
        imported = self._import.options if self._import else {}
        if user_input is not None:
            data: dict[str, Any] = {CONF_VIN: self._vin}
            if self._import:
                data["imported"] = self._import.stored()
                if self._disable_automation:
                    await self.hass.services.async_call(
                        "automation",
                        "turn_off",
                        {"entity_id": self._import.entity_id},
                        blocking=True,
                    )
            return self.async_create_entry(
                title=ford_vehicles(self.hass).get(self._vin, self._vin),
                data=data,
                options={
                    CONF_PRECONDITION_DAYS: imported.get(CONF_PRECONDITION_DAYS, DEFAULT_DAYS),
                    CONF_WORK_PROMPT_DAYS: imported.get(CONF_WORK_PROMPT_DAYS, DEFAULT_DAYS),
                    CONF_ALARM_NORMAL_STATES: imported.get(
                        CONF_ALARM_NORMAL_STATES, DEFAULT_ALARM_NORMAL_STATES
                    ),
                    **user_input,
                },
            )
        schema = _settings_schema()
        if imported:
            schema = self.add_suggested_values_to_schema(schema, imported)
        return self.async_show_form(step_id="settings", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> FordAssistantOptionsFlow:
        """Options flow."""
        return FordAssistantOptionsFlow()


class FordAssistantOptionsFlow(OptionsFlowWithReload):
    """Change alert targets, places and schedules."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = _settings_schema().extend(
            {
                vol.Required(
                    CONF_PRECONDITION_DAYS, default=DEFAULT_DAYS
                ): DAY_SELECTOR,
                vol.Required(
                    CONF_WORK_PROMPT_DAYS, default=DEFAULT_DAYS
                ): DAY_SELECTOR,
                vol.Required(
                    CONF_ALARM_NORMAL_STATES, default=DEFAULT_ALARM_NORMAL_STATES
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=DEFAULT_ALARM_NORMAL_STATES,
                        multiple=True,
                        custom_value=True,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
        )
