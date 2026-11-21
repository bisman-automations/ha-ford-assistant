"""Diagnostics for Ford Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import FordAssistantConfigEntry
from .const import CONF_PHONE_TRACKER, CONF_VIN

TO_REDACT = {
    CONF_VIN,
    "latitude",
    "longitude",
    CONF_PHONE_TRACKER,
    "active_driver_name",
}


def _hide_drivers(data: Any, names: dict[str, str]) -> Any:
    """Swap household drivers' person entity IDs for numbered placeholders.

    Their entity IDs are usually the people's names (``person.alex``), and
    diagnostics end up attached to public issues. Which driver is which, and
    their profiles, stay readable as ``person.driver_1`` and so on.
    """
    if isinstance(data, dict):
        return {
            names.get(key, key) if isinstance(key, str) else key: _hide_drivers(
                value, names
            )
            for key, value in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [_hide_drivers(item, names) for item in data]
    if isinstance(data, str):
        return names.get(data, data)
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FordAssistantConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data
    drivers = {
        person: f"person.driver_{number}"
        for number, person in enumerate(controller.household_drivers, start=1)
    }
    states = {}
    for role, entity_id in controller.entities.items():
        state = hass.states.get(entity_id)
        states[role] = (
            None
            if state is None
            else {
                "state": state.state,
                "attributes": async_redact_data(dict(state.attributes), TO_REDACT),
            }
        )
    return {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": _hide_drivers(
            async_redact_data(dict(entry.options), TO_REDACT), drivers
        ),
        "features": controller.features,
        "numbers": controller.numbers,
        "times": {k: v.isoformat() for k, v in controller.times.items()},
        "latched": controller.latched,
        "ford_entities": {
            role: e.replace(controller.vin.lower(), "<vin>")
            for role, e in controller.entities.items()
        },
        "ford_states": states,
        "last_event": None
        if controller.last_event is None
        else {
            **controller.last_event,
            "time": controller.last_event["time"].isoformat(),
        },
        "driving": _hide_drivers(
            async_redact_data(controller.driving_attributes(), TO_REDACT), drivers
        ),
    }
