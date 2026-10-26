"""The Ford Assistant sidebar dashboard.

Registers one "Ford Assistant" panel in the sidebar while at least one vehicle
is set up, serves its JavaScript, and answers the panel's websocket request for
the vehicles and their entities. The panel reads live states and calls services
through the frontend's own connection, so it needs no other backend.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_GARAGE,
    CONF_HOME_ZONE,
    DOMAIN,
    EV_FEATURES,
    EV_NUMBERS,
    EV_TIMES,
    FEATURES,
    NUMBERS,
    TIMES,
)
from .discovery import ford_device

_LOGGER = logging.getLogger(__name__)

PANEL_URL_PATH = "ford-assistant"
PANEL_COMPONENT = "ford-assistant-panel"
PANEL_TITLE = "Ford Assistant"
PANEL_ICON = "mdi:car-connected"
STATIC_URL = "/ford_assistant_static"
FRONTEND_DIR = Path(__file__).parent / "frontend"
DATA_PANEL = f"{DOMAIN}_panel"
DATA_STATIC = f"{DOMAIN}_static"


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register the panel's websocket command (once per run)."""
    websocket_api.async_register_command(hass, websocket_vehicles)


async def async_register_panel(hass: HomeAssistant, version: str | None) -> None:
    """Show the panel in the sidebar (no-op if it's already there)."""
    if hass.data.get(DATA_PANEL):
        return
    if "frontend" not in hass.config.components or hass.http is None:
        # Not running with a frontend (e.g. tests or a headless setup).
        return

    from homeassistant.components import panel_custom
    from homeassistant.components.http import StaticPathConfig

    if not hass.data.get(DATA_STATIC):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
        )
        hass.data[DATA_STATIC] = True

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        # The version busts the browser cache after an update.
        module_url=f"{STATIC_URL}/ford-assistant-panel.js?v={version or 'dev'}",
        require_admin=False,
        config={},
    )
    hass.data[DATA_PANEL] = True


@callback
def async_unregister_panel_if_unused(
    hass: HomeAssistant, leaving_entry_id: str
) -> None:
    """Remove the panel once no vehicle is set up any more."""
    if not hass.data.get(DATA_PANEL):
        return
    still_loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != leaving_entry_id and entry.state is ConfigEntryState.LOADED
    ]
    if still_loaded:
        return
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    hass.data[DATA_PANEL] = False


def _ours(registry: er.EntityRegistry, platform: str, vin: str, key: str) -> str | None:
    return registry.async_get_entity_id(platform, DOMAIN, f"{vin}_{key}".lower())


@callback
def vehicle_summary(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Everything the panel needs to know about one vehicle."""
    controller = entry.runtime_data
    vin = controller.vin
    registry = er.async_get(hass)
    electric = controller.is_electric

    def assistant(platform: str, keys, ev_keys) -> dict[str, str]:
        found: dict[str, str] = {}
        for key in keys:
            if key in ev_keys and not electric:
                continue
            if entity_id := _ours(registry, platform, vin, key):
                found[key] = entity_id
        return found

    vehicle = ford_device(hass, vin)
    last_event = _ours(registry, "sensor", vin, "last_event")
    assistant_device = None
    if last_event and (reg_entry := registry.async_get(last_event)):
        assistant_device = reg_entry.device_id

    return {
        "entry_id": entry.entry_id,
        "name": controller.name,
        "manufacturer": vehicle.manufacturer if vehicle else None,
        "model": vehicle.model if vehicle else None,
        "ford_device_id": vehicle.id if vehicle else None,
        "assistant_device_id": assistant_device,
        "electric": electric,
        "home_zone": controller.options.get(CONF_HOME_ZONE) or "zone.home",
        "garage": controller.options.get(CONF_GARAGE),
        "ford": dict(controller.entities),
        "assistant": {
            "switch": assistant("switch", FEATURES, EV_FEATURES),
            "number": assistant("number", NUMBERS, EV_NUMBERS),
            "time": assistant("time", TIMES, EV_TIMES),
            "sensor": {"last_event": last_event} if last_event else {},
        },
    }


@websocket_api.websocket_command({vol.Required("type"): "ford_assistant/vehicles"})
@callback
def websocket_vehicles(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List the set-up vehicles for the panel."""
    vehicles = [
        vehicle_summary(hass, entry)
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    vehicles.sort(key=lambda v: v["name"].casefold())
    connection.send_result(msg["id"], {"vehicles": vehicles})
