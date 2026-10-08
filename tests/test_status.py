"""Tests for the always-on vehicle status Live Activity."""

from __future__ import annotations

from datetime import timedelta

from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant

from .test_init import HOME, VIN, _clears, _entity_id, _setup, ford  # noqa: F401, F811

TAG = f"ford-status-{VIN}"


def _status(calls) -> list:
    return [c for c in calls if c.data.get("data", {}).get("tag") == TAG and c.data["data"].get("live_update")]


async def _later(hass: HomeAssistant, freezer: FrozenDateTimeFactory, **delta) -> None:
    await hass.async_block_till_done()  # let state changes schedule their timers first
    freezer.tick(timedelta(**delta))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_off_by_default(hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)
    hass.states.async_set(_entity_id("lock"), "locked")
    await _later(hass, freezer, seconds=10)
    assert not _status(notify_calls)


async def test_status_content_and_updates(hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    entry.runtime_data.set_feature("status_activity", True)
    await hass.async_block_till_done()

    first = _status(notify_calls)
    assert len(first) == 1
    data = first[0].data["data"]
    assert first[0].data["title"] == "2022 Escape (000001)"
    assert data["critical_text"] == "Unlocked"  # unlocked away from home
    assert data["color"] == "#E5484D"
    assert data["progress"] == 50 and data["progress_max"] == 100
    assert first[0].data["message"] == "⛽ 50% · 200 km · 📍 Away · 20°"
    assert [a["title"] for a in data["actions"]] == ["Lock", "Start"]

    # Locking is shown right away (after the short debounce).
    hass.states.async_set(_entity_id("lock"), "locked")
    await _later(hass, freezer, seconds=6)
    latest = _status(notify_calls)[-1]
    assert latest.data["data"]["critical_text"] == "Locked"
    assert "silent" not in latest.data["data"]

    # A small fuel change waits for the rate limit, then goes out quietly.
    count = len(_status(notify_calls))
    hass.states.async_set(_entity_id("fuel"), "48", {"fuelRange": 190})
    await _later(hass, freezer, seconds=12)
    assert len(_status(notify_calls)) == count
    await _later(hass, freezer, minutes=16)
    latest = _status(notify_calls)[-1]
    assert latest.data["message"].startswith("⛽ 48% · 190 km")
    assert latest.data["data"]["silent"] is True


async def test_remote_start_shown_in_status(hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    entry.runtime_data.set_feature("status_activity", True)
    await hass.async_block_till_done()

    hass.states.async_set(_entity_id("countdown"), "15", {"unit_of_measurement": "min"})
    hass.states.async_set(_entity_id("remote_start"), "on")
    await _later(hass, freezer, seconds=6)

    latest = _status(notify_calls)[-1].data["data"]
    assert latest["critical_text"] == "Running"
    assert latest["chronometer"] and 840 <= latest["when"] <= 900
    assert [a["title"] for a in latest["actions"]] == ["Lock", "Stop"]
    # No separate remote start activity while the status one is on.
    assert not [c for c in notify_calls if c.data.get("data", {}).get("tag") == f"ford-activity-{VIN}"]


async def test_restarts_before_ios_limit(hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory) -> None:
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    entry.runtime_data.set_feature("status_activity", True)
    await hass.async_block_till_done()
    assert not _clears(notify_calls)

    for _ in range(32):  # 8 hours in 15-minute steps
        await _later(hass, freezer, minutes=15)
    assert _clears(notify_calls) == [TAG]
    assert _status(notify_calls)[-1].data["data"]["critical_text"]


async def test_turn_off_clears(hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory) -> None:
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    entry.runtime_data.set_feature("status_activity", True)
    await hass.async_block_till_done()
    entry.runtime_data.set_feature("status_activity", False)
    await hass.async_block_till_done()
    assert _clears(notify_calls) == [TAG]


async def test_status_at_home_and_doors(hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory) -> None:
    hass.states.async_set(_entity_id("tracker"), "home", {**HOME, "gps_accuracy": 5})
    hass.states.async_set(_entity_id("lock"), "locked")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    entry.runtime_data.set_feature("status_activity", True)
    await hass.async_block_till_done()
    first = _status(notify_calls)[-1]
    assert first.data["data"]["critical_text"] == "Locked"
    assert first.data["data"]["color"] == "#1F6FD1"
    assert "🏠 Home" in first.data["message"]

    hass.states.async_set(_entity_id("doors"), "Open", {"tailgate": "OPEN"})
    await _later(hass, freezer, seconds=6)
    latest = _status(notify_calls)[-1]
    assert latest.data["data"]["critical_text"] == "Door open"
    assert latest.data["message"].startswith("🚪 Tailgate open · 🔒 Locked")
