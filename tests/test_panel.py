"""Tests for the sidebar dashboard backend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from custom_components.ford_assistant import panel
from custom_components.ford_assistant.const import FORD_ENTITY_KEYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_init import VIN, _ours, _setup, ford  # noqa: F401, F811


async def test_vehicles_websocket(
    hass: HomeAssistant, ford: str, hass_ws_client
) -> None:
    await _setup(hass, ford)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "ford_assistant/vehicles"})
    msg = await client.receive_json()
    assert msg["success"]
    (vehicle,) = msg["result"]["vehicles"]

    assert vehicle["name"] == "2022 Escape (000001)"
    assert vehicle["model"] == "2022 Escape"
    assert vehicle["electric"] is False
    assert vehicle["home_zone"] == "zone.home"
    assert vehicle["ford"]["lock"] == f"lock.fordpass_{VIN.lower()}_doorlock"
    assert set(vehicle["ford"]) <= set(FORD_ENTITY_KEYS)
    switches = vehicle["assistant"]["switch"]
    assert switches["auto_lock"] == _ours(hass, "switch", "auto_lock")
    assert "plug_in_reminder" not in switches  # EV-only, and this is a gas vehicle
    assert vehicle["assistant"]["number"]["fuel_threshold"] == _ours(
        hass, "number", "fuel_threshold"
    )
    assert vehicle["assistant"]["sensor"]["last_event"] == _ours(
        hass, "sensor", "last_event"
    )
    own = er.async_get(hass).async_get(_ours(hass, "sensor", "last_event"))
    assert vehicle["assistant_device_id"] == own.device_id


async def test_no_vehicles(hass: HomeAssistant, hass_ws_client) -> None:
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "ford_assistant", {})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "ford_assistant/vehicles"})
    msg = await client.receive_json()
    assert msg["result"] == {"vehicles": []}


async def test_panel_registered_and_removed(hass: HomeAssistant, ford: str) -> None:
    """With a frontend, the panel appears with the first vehicle and goes with the last."""
    hass.config.components.add("frontend")
    static = AsyncMock()
    with (
        patch(
            "homeassistant.components.http.HomeAssistantHTTP.async_register_static_paths",
            static,
        ),
        patch(
            "homeassistant.components.panel_custom.async_register_panel", AsyncMock()
        ) as register,
        patch("homeassistant.components.frontend.async_remove_panel") as remove,
    ):
        entry = await _setup(hass, ford)
        register.assert_awaited_once()
        kwargs = register.await_args.kwargs
        assert kwargs["frontend_url_path"] == "ford-assistant"
        assert kwargs["webcomponent_name"] == "ford-assistant-panel"
        assert kwargs["module_url"].startswith(
            "/ford_assistant_static/ford-assistant-panel.js?v="
        )
        static.assert_awaited_once()
        (config,) = static.await_args.args[0]
        assert config.url_path == "/ford_assistant_static"
        assert Path(config.path) == panel.FRONTEND_DIR

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        remove.assert_called_once()
        assert remove.call_args.args[1] == "ford-assistant"


async def test_no_panel_without_frontend(hass: HomeAssistant, ford: str) -> None:
    with patch(
        "homeassistant.components.panel_custom.async_register_panel", AsyncMock()
    ) as register:
        await _setup(hass, ford)
    register.assert_not_awaited()


def test_frontend_file_is_shipped() -> None:
    js = Path(panel.FRONTEND_DIR) / "ford-assistant-panel.js"
    assert js.is_file()
    assert 'customElements.define("ford-assistant-panel"' in js.read_text()
