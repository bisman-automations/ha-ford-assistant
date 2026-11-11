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
    CONF_DRIVER_PROFILES,
    CONF_GARAGE,
    CONF_GUEST_ACTIONS,
    CONF_GUEST_ALERTS,
    CONF_GUEST_REVERT,
    CONF_HOME_ZONE,
    CONF_HOUSEHOLD_DRIVERS,
    CONF_NOTIFY_DEVICES,
    CONF_PHONE_TRACKER,
    CONF_PRECONDITION_DAYS,
    CONF_SERVICE_ACTIONS,
    CONF_SERVICE_ALERTS,
    CONF_SERVICE_REVERT,
    CONF_SOURCE,
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
from .driving import (
    ACTIONS,
    ALERTS,
    GUEST_DEFAULT_ACTIONS,
    GUEST_DEFAULT_ALERTS,
    SERVICE_DEFAULT_ACTIONS,
    SERVICE_DEFAULT_ALERTS,
)
from .importer import BlueprintSettings, find_blueprint_automations
from .sources import SOURCE_CHINA, SOURCE_FORDPASS, SOURCE_LABELS, cn_entity

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

ALERT_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=list(ALERTS),
        multiple=True,
        mode=selector.SelectSelectorMode.LIST,
        translation_key="driving_alert",
    )
)

ACTION_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=list(ACTIONS),
        multiple=True,
        mode=selector.SelectSelectorMode.LIST,
        translation_key="driving_action",
    )
)

# Keys written by the phones, places and schedules step. Saving that step
# replaces these and leaves the driving-mode options alone. Clearing an
# optional field omits it, which removes the previous value.
_SETTINGS_KEYS = (
    CONF_NOTIFY_DEVICES,
    CONF_PHONE_TRACKER,
    CONF_HOME_ZONE,
    CONF_WORK_ZONE,
    CONF_WEATHER,
    CONF_TODO,
    CONF_GARAGE,
    CONF_PRECONDITION_DAYS,
    CONF_WORK_PROMPT_DAYS,
    CONF_ALARM_NORMAL_STATES,
)


def _choice_schema(
    alerts_key: str,
    actions_key: str,
    revert_key: str,
    default_alerts: tuple[str, ...],
    default_actions: tuple[str, ...],
) -> vol.Schema:
    """Alerts to keep, actions to allow, and an optional return to Household."""
    return vol.Schema(
        {
            vol.Required(alerts_key, default=list(default_alerts)): ALERT_SELECTOR,
            vol.Required(actions_key, default=list(default_actions)): ACTION_SELECTOR,
            vol.Optional(revert_key): selector.DurationSelector(
                selector.DurationSelectorConfig(enable_day=True)
            ),
        }
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
        self._source: str = SOURCE_FORDPASS
        self._vehicle_name: str | None = None
        self._blueprints: list[BlueprintSettings] = []
        self._import: BlueprintSettings | None = None
        self._disable_automation = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the vehicle."""
        configured = {e.unique_id for e in self._async_current_entries()}
        vehicles = {
            token: vehicle
            for token, vehicle in ford_vehicles(self.hass).items()
            if vehicle.unique_id not in configured
        }
        if not vehicles:
            reason = "already_configured" if configured else "no_vehicles"
            return self.async_abort(reason=reason)

        # Say which Ford integration a vehicle comes from when both are present.
        show_source = len({vehicle.source for vehicle in vehicles.values()}) > 1

        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_VIN]
            vehicle = vehicles.get(token)
            if vehicle is None:
                return self.async_abort(reason="no_vehicles")
            source = vehicle.source
            await self.async_set_unique_id(vehicle.unique_id)
            self._abort_if_unique_id_configured()
            entities = resolve_entities(self.hass, token, source)
            if source == SOURCE_CHINA:
                supported = "tracker" in entities and all(
                    cn_entity(self.hass, token, key)
                    for key in ("lock_status", "lock_door", "unlock_door")
                )
            else:
                supported = "lock" in entities and "tracker" in entities
            if not supported:
                errors["base"] = "missing_entities"
            else:
                self._vin = token
                self._source = source
                self._vehicle_name = vehicle.name
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
                                selector.SelectOptionDict(
                                    value=token,
                                    label=(
                                        f"{vehicle.name} · {SOURCE_LABELS[vehicle.source]}"
                                        if show_source
                                        else vehicle.name
                                    ),
                                )
                                for token, vehicle in vehicles.items()
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
            data: dict[str, Any] = {CONF_VIN: self._vin, CONF_SOURCE: self._source}
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
                title=self._vehicle_name or self._vin,
                data=data,
                options={
                    CONF_PRECONDITION_DAYS: imported.get(
                        CONF_PRECONDITION_DAYS, DEFAULT_DAYS
                    ),
                    CONF_WORK_PROMPT_DAYS: imported.get(
                        CONF_WORK_PROMPT_DAYS, DEFAULT_DAYS
                    ),
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
    """Phones and places, household drivers, and Service and Guest mode."""

    def __init__(self) -> None:
        """Initialise the flow."""
        self._drivers: list[str] = []
        self._profiles: dict[str, dict[str, Any]] = {}
        self._profile_index = 0

    def _save(self, owned: tuple[str, ...], user_input: dict[str, Any]):
        """Replace the keys this step owns and keep every other option."""
        data = {
            key: value
            for key, value in self.config_entry.options.items()
            if key not in owned
        }
        data.update(user_input)
        return self.async_create_entry(data=data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose what to change."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "settings",
                "household_drivers",
                "service_mode",
                "guest_mode",
            ],
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Phones, places, days and normal alarm states."""
        if user_input is not None:
            return self._save(_SETTINGS_KEYS, user_input)
        schema = _settings_schema().extend(
            {
                vol.Required(
                    CONF_PRECONDITION_DAYS, default=DEFAULT_DAYS
                ): DAY_SELECTOR,
                vol.Required(CONF_WORK_PROMPT_DAYS, default=DEFAULT_DAYS): DAY_SELECTOR,
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
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
        )

    async def async_step_household_drivers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose which people may drive, then a profile for each."""
        if user_input is not None:
            self._drivers = list(user_input[CONF_HOUSEHOLD_DRIVERS])
            existing = self.config_entry.options.get(CONF_DRIVER_PROFILES) or {}
            if not isinstance(existing, dict):
                existing = {}
            self._profiles = {
                person: existing[person]
                for person in self._drivers
                if isinstance(existing.get(person), dict)
            }
            self._profile_index = 0
            if self._drivers:
                return await self.async_step_driver_profile()
            return self._save(
                (CONF_HOUSEHOLD_DRIVERS, CONF_DRIVER_PROFILES),
                {CONF_HOUSEHOLD_DRIVERS: [], CONF_DRIVER_PROFILES: {}},
            )
        return self.async_show_form(
            step_id="household_drivers",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_HOUSEHOLD_DRIVERS, default=[]
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="person", multiple=True
                            )
                        )
                    }
                ),
                self.config_entry.options,
            ),
        )

    async def async_step_driver_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Alerts, phones and actions for one household driver."""
        person = self._drivers[self._profile_index]
        if user_input is not None:
            self._profiles[person] = {
                "alerts": list(user_input["alerts"]),
                "notify_devices": list(user_input.get("notify_devices") or []),
                "actions": list(user_input["actions"]),
            }
            self._profile_index += 1
            if self._profile_index < len(self._drivers):
                return await self.async_step_driver_profile()
            return self._save(
                (CONF_HOUSEHOLD_DRIVERS, CONF_DRIVER_PROFILES),
                {
                    CONF_HOUSEHOLD_DRIVERS: self._drivers,
                    CONF_DRIVER_PROFILES: self._profiles,
                },
            )
        state = self.hass.states.get(person)
        saved = self._profiles.get(person) or {}
        schema = vol.Schema(
            {
                vol.Required("alerts", default=list(ALERTS)): ALERT_SELECTOR,
                vol.Optional("notify_devices", default=[]): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(
                        integration="mobile_app", multiple=True
                    )
                ),
                vol.Required("actions", default=list(ACTIONS)): ACTION_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="driver_profile",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    "alerts": saved.get("alerts", list(ALERTS)),
                    "notify_devices": saved.get("notify_devices", []),
                    "actions": saved.get("actions", list(ACTIONS)),
                },
            ),
            description_placeholders={
                "person": state.name if state else person,
            },
        )

    async def async_step_service_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """What Service mode keeps and allows, and when it returns to Household."""
        return await self._async_mode_step(
            "service_mode",
            user_input,
            CONF_SERVICE_ALERTS,
            CONF_SERVICE_ACTIONS,
            CONF_SERVICE_REVERT,
            SERVICE_DEFAULT_ALERTS,
            SERVICE_DEFAULT_ACTIONS,
        )

    async def async_step_guest_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """What Guest mode keeps and allows, and when it returns to Household."""
        return await self._async_mode_step(
            "guest_mode",
            user_input,
            CONF_GUEST_ALERTS,
            CONF_GUEST_ACTIONS,
            CONF_GUEST_REVERT,
            GUEST_DEFAULT_ALERTS,
            GUEST_DEFAULT_ACTIONS,
        )

    async def _async_mode_step(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
        alerts_key: str,
        actions_key: str,
        revert_key: str,
        default_alerts: tuple[str, ...],
        default_actions: tuple[str, ...],
    ) -> ConfigFlowResult:
        owned = (alerts_key, actions_key, revert_key)
        if user_input is not None:
            return self._save(owned, user_input)
        schema = _choice_schema(
            alerts_key, actions_key, revert_key, default_alerts, default_actions
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
        )
