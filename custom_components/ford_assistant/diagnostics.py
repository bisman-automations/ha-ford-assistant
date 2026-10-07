"""Diagnostics for Ford Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import FordAssistantConfigEntry
from .const import CONF_VIN

TO_REDACT = {CONF_VIN, "latitude", "longitude"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FordAssistantConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data
    states = {}
    for role, entity_id in controller.entities.items():
        state = hass.states.get(entity_id)
        states[role] = None if state is None else {
            "state": state.state,
            "attributes": async_redact_data(dict(state.attributes), TO_REDACT),
        }
    return {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "features": controller.features,
        "numbers": controller.numbers,
        "times": {k: v.isoformat() for k, v in controller.times.items()},
        "latched": controller.latched,
        "ford_entities": {role: e.replace(controller.vin.lower(), "<vin>") for role, e in controller.entities.items()},
        "ford_states": states,
        "last_event": None
        if controller.last_event is None
        else {**controller.last_event, "time": controller.last_event["time"].isoformat()},
    }
