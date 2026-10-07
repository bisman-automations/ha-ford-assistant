"""Copy settings from a 'FordPass – Vehicle Assistant' blueprint automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ALARM_NORMAL_STATES,
    CONF_GARAGE,
    CONF_HOME_ZONE,
    CONF_NOTIFY_DEVICES,
    CONF_PHONE_TRACKER,
    CONF_PRECONDITION_DAYS,
    CONF_TODO,
    CONF_WEATHER,
    CONF_WORK_PROMPT_DAYS,
    CONF_WORK_ZONE,
)

# blueprint input -> Ford Assistant option
OPTION_INPUTS = {
    "notify_device": CONF_NOTIFY_DEVICES,
    "phone_tracker": CONF_PHONE_TRACKER,
    "home_zone": CONF_HOME_ZONE,
    "work_zone": CONF_WORK_ZONE,
    "weather_entity": CONF_WEATHER,
    "todo_entity": CONF_TODO,
    "garage_cover": CONF_GARAGE,
    "precondition_days": CONF_PRECONDITION_DAYS,
    "work_prompt_days": CONF_WORK_PROMPT_DAYS,
    "alarm_normal_states": CONF_ALARM_NORMAL_STATES,
}
FEATURE_INPUTS = {
    "en_autolock": "auto_lock",
    "en_precondition": "precondition",
    "en_work_prompt": "work_prompt",
    "en_extend": "auto_extend",
    "en_alarm": "alarm_alert",
    "en_windows": "windows_alert",
    "en_fuel": "fuel_alert",
    "en_oil": "oil_alert",
    "en_battery": "battery_alert",
    "en_tires": "tire_alert",
    "en_indicators": "indicator_alert",
    "garage_open_on_arrival": "garage_open",
}
NUMBER_INPUTS = {
    "walk_away_distance": "walk_away_distance",
    "cold_temp": "cold_threshold",
    "hot_temp": "hot_threshold",
    "min_fuel_start": "min_fuel_to_start",
    "extend_below": "extend_below",
    "fuel_below": "fuel_threshold",
    "oil_below": "oil_threshold",
    "battery_below": "battery_threshold",
}
DURATION_INPUTS = {"autolock_wait": "auto_lock_delay"}
TIME_INPUTS = {
    "precondition_time": "precondition_time",
    "work_prompt_time": "work_prompt_time",
}


@dataclass
class BlueprintSettings:
    """What was found in one blueprint automation."""

    entity_id: str
    name: str
    options: dict[str, Any] = field(default_factory=dict)
    features: dict[str, bool] = field(default_factory=dict)
    numbers: dict[str, float] = field(default_factory=dict)
    times: dict[str, str] = field(default_factory=dict)

    def stored(self) -> dict[str, Any]:
        """Settings to apply to the controller on its first start."""
        return {"features": self.features, "numbers": self.numbers, "times": self.times}


def find_blueprint_automations(
    hass: HomeAssistant, lock_entity_id: str | None
) -> list[BlueprintSettings]:
    """Blueprint automations that control this vehicle's lock."""
    from homeassistant.components.automation import DATA_COMPONENT

    if lock_entity_id is None or (component := hass.data.get(DATA_COMPONENT)) is None:
        return []
    found: list[BlueprintSettings] = []
    for entity in component.entities:
        raw = getattr(entity, "raw_config", None) or {}
        inputs = (raw.get("use_blueprint") or {}).get("input") or {}
        if inputs.get("lock_entity") != lock_entity_id:
            continue
        name = (entity.name if isinstance(entity.name, str) else None) or raw.get("alias") or entity.entity_id
        found.append(convert(entity.entity_id, name, inputs))
    return found


def _minutes(value: Any) -> float | None:
    try:
        return cv.time_period(value).total_seconds() / 60
    except vol.Invalid:
        return None


def _time(value: Any) -> str | None:
    try:
        return time.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None


def convert(entity_id: str, name: str, inputs: dict[str, Any]) -> BlueprintSettings:
    """Map blueprint inputs onto Ford Assistant settings.

    Only inputs that were actually set are copied; everything else keeps Ford
    Assistant's defaults (which match the blueprint's).
    """
    result = BlueprintSettings(entity_id, name)

    for key, option in OPTION_INPUTS.items():
        value = inputs.get(key)
        if value in (None, "", []):
            continue
        if option == CONF_NOTIFY_DEVICES and isinstance(value, str):
            value = [value]
        result.options[option] = value

    for key, feature in FEATURE_INPUTS.items():
        if key in inputs:
            result.features[feature] = bool(inputs[key])

    for key, number in NUMBER_INPUTS.items():
        try:
            result.numbers[number] = float(inputs[key])
        except (KeyError, TypeError, ValueError):
            continue

    for key, number in DURATION_INPUTS.items():
        if key in inputs and (minutes := _minutes(inputs[key])) is not None:
            result.numbers[number] = max(1.0, minutes)

    if "garage_close_after" in inputs and (minutes := _minutes(inputs["garage_close_after"])) is not None:
        if minutes <= 0:
            result.features["garage_close"] = False
        else:
            result.numbers["garage_close_delay"] = minutes

    for key, setting in TIME_INPUTS.items():
        if key in inputs and (value := _time(inputs[key])) is not None:
            result.times[setting] = value

    return result
