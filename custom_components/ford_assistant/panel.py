"""The Ford Assistant sidebar dashboard.

Registers one "Ford Assistant" panel in the sidebar while at least one vehicle
is set up, serves its JavaScript, and answers the panel's websocket request for
the vehicles and their entities. The panel reads live states and calls services
through the frontend's own connection, so it needs no other backend.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er

from .access import async_get_access, get_access
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
    """Register the panel's websocket commands (once per run)."""
    for command in (
        websocket_vehicles,
        websocket_access_me,
        websocket_access_get,
        websocket_access_set,
    ):
        websocket_api.async_register_command(hass, command)


def require_access(func: Callable) -> Callable:
    """Only admins and the people an admin allowed may use the dashboard."""

    @wraps(func)
    def with_access(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        if not get_access(hass).allows(connection.user):
            raise Unauthorized
        func(hass, connection, msg)

    return with_access


async def async_register_panel(
    hass: HomeAssistant, version: str | None, *, update: bool = False
) -> None:
    """Show the panel in the sidebar (no-op if it's already there).

    It's admin-only unless an admin let someone who isn't an admin in. Home
    Assistant can't show a sidebar entry to only some people, so then everyone
    sees it, and the dashboard tells anyone not allowed that they don't have
    access.
    """
    access = await async_get_access(hass)
    if "frontend" not in hass.config.components or hass.http is None:
        # Not running with a frontend (e.g. tests or a headless setup).
        return
    require_admin = not await access.async_listed_non_admins()
    wanted = "admin" if require_admin else "all"
    registered = hass.data.get(DATA_PANEL)
    if registered == wanted or (registered and not update):
        return

    from homeassistant.components import frontend, panel_custom
    from homeassistant.components.http import StaticPathConfig

    if not hass.data.get(DATA_STATIC):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
        )
        hass.data[DATA_STATIC] = True
    if registered:
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    if version is not None:
        hass.data[f"{DATA_PANEL}_version"] = version
    version = hass.data.get(f"{DATA_PANEL}_version")

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        # The version busts the browser cache after an update.
        module_url=f"{STATIC_URL}/ford-assistant-panel.js?v={version or 'dev'}",
        require_admin=require_admin,
        config={},
    )
    hass.data[DATA_PANEL] = wanted


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
@require_access
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


# ---- who may use Ford Assistant -----------------------------------------------------


@websocket_api.websocket_command({vol.Required("type"): "ford_assistant/access/me"})
@callback
def websocket_access_me(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Whether the person viewing may use the dashboard, so it can say so."""
    user = connection.user
    connection.send_result(
        msg["id"],
        {
            "allowed": get_access(hass).allows(user),
            "is_admin": bool(user and user.is_admin),
        },
    )


async def _people(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Home Assistant logins an admin can let in (admins always can)."""
    users = [
        u
        for u in await hass.auth.async_get_users()
        if not u.system_generated and u.is_active
    ]
    return [
        {"id": u.id, "name": u.name or u.id, "is_admin": u.is_admin}
        for u in sorted(users, key=lambda u: (u.name or "").casefold())
    ]


@websocket_api.websocket_command({vol.Required("type"): "ford_assistant/access/get"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_access_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    connection.send_result(
        msg["id"],
        {"user_ids": list(get_access(hass).user_ids), "people": await _people(hass)},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ford_assistant/access/set",
        vol.Required("user_ids"): [str],
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_access_set(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    access = get_access(hass)
    await access.async_set(msg["user_ids"])
    await async_register_panel(hass, None, update=True)
    connection.send_result(
        msg["id"], {"user_ids": list(access.user_ids), "people": await _people(hass)}
    )
