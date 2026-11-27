"""iPhones get an Open button so a tap can show the notification's buttons."""

from __future__ import annotations

from datetime import timedelta

from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.ford_assistant.logic import for_apple, is_apple
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .test_init import VIN, _setup, ford  # noqa: F401


def _phone_on(hass: HomeAssistant, os_name: str) -> None:
    [entry] = hass.config_entries.async_entries("mobile_app")
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "os_name": os_name}
    )


async def test_iphone_gets_open_instead_of_a_tap_url(
    hass: HomeAssistant, ford: str
) -> None:
    _phone_on(hass, "iOS")
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=4))
    await hass.async_block_till_done()

    [call] = notify_calls
    data = call.data["data"]
    assert "url" not in data
    assert "clickAction" not in data
    actions = data["actions"]
    assert actions[0]["action"] == f"FORD_ASSISTANT_HONK_{VIN}"
    assert actions[-1]["action"] == "URI"
    assert actions[-1]["title"] == "Open"
    assert actions[-1]["uri"].startswith("/config/devices/device/")


async def test_android_keeps_the_tap_url(hass: HomeAssistant, ford: str) -> None:
    _phone_on(hass, "Android")
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=4))
    await hass.async_block_till_done()

    [call] = notify_calls
    data = call.data["data"]
    assert data["clickAction"].startswith("/config/devices/device/")
    assert data["url"] == data["clickAction"]
    assert all(action["action"] != "URI" for action in data["actions"])


def test_only_notifications_with_buttons_and_a_page_change() -> None:
    assert is_apple("iOS") and is_apple("iPadOS") and is_apple("macOS")
    assert not is_apple("Android") and not is_apple(None)
    plain = {"message": "x", "data": {"url": "/a"}}
    assert for_apple(plain, "Open") is plain
    live = {"message": "x", "data": {"live_update": True, "url": "/a", "actions": [{}]}}
    assert for_apple(live, "Open") is live
    no_page = {"message": "x", "data": {"actions": [{"action": "A"}]}}
    assert for_apple(no_page, "Open") is no_page
