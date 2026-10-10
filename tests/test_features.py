"""Tests for quiet hours, the remote start Live Activity, EV support and blueprint import."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import async_mock_service

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.ford_assistant.const import CONF_NOTIFY_DEVICES, DOMAIN
from custom_components.ford_assistant.importer import convert
from custom_components.ford_assistant.logic import in_quiet_hours

from custom_components.ford_assistant.discovery import ford_device as ford_vehicle_device

from .test_init import HOME, VIN, _clears, _entity_id, _ours, _setup, ford  # noqa: F401, F811

LIVE = "ford-activity-" + VIN


def _quiet_now(controller) -> None:
    now = dt_util.now()
    controller.set_time("quiet_start", (now - timedelta(hours=1)).time().replace(microsecond=0))
    controller.set_time("quiet_end", (now + timedelta(hours=1)).time().replace(microsecond=0))
    controller.set_feature("quiet_hours", True)


def test_in_quiet_hours_spans_midnight() -> None:
    from datetime import time

    assert in_quiet_hours(time(23), time(22), time(7))
    assert in_quiet_hours(time(6, 59), time(22), time(7))
    assert not in_quiet_hours(time(7), time(22), time(7))
    assert in_quiet_hours(time(13), time(12), time(14))
    assert not in_quiet_hours(time(13), time(12), time(12))


async def test_quiet_hours_hold_then_deliver(hass: HomeAssistant, ford: str) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    controller = entry.runtime_data
    _quiet_now(controller)

    hass.states.async_set(_entity_id("fuel"), "10", {})
    await hass.async_block_till_done()
    assert not [c for c in notify_calls if "fuel" in c.data.get("title", "")]
    assert "fuel" in controller._deferred

    # Critical alerts still go straight through.
    hass.states.async_set(_entity_id("alarm"), "SET_OFF")
    await hass.async_block_till_done()
    assert any("alarm" in c.data.get("title", "") for c in notify_calls)

    controller.set_feature("quiet_hours", False)
    await hass.async_block_till_done()
    assert [c for c in notify_calls if "fuel" in c.data.get("title", "")]
    assert not controller._deferred


async def test_quiet_hours_drop_resolved(hass: HomeAssistant, ford: str) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    _quiet_now(entry.runtime_data)
    hass.states.async_set(_entity_id("fuel"), "10", {})
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("fuel"), "90", {})
    await hass.async_block_till_done()
    entry.runtime_data.set_feature("quiet_hours", False)
    await hass.async_block_till_done()
    assert not [c for c in notify_calls if "fuel" in c.data.get("title", "")]


async def test_remote_start_live_activity(hass: HomeAssistant, ford: str) -> None:
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)
    unit = {"unit_of_measurement": "min"}

    hass.states.async_set(_entity_id("countdown"), "15", unit)
    hass.states.async_set(_entity_id("remote_start"), "on")
    await hass.async_block_till_done()
    live = [c for c in notify_calls if c.data["data"].get("live_update")]
    assert len(live) == 1
    data = live[0].data["data"]
    assert data["tag"] == LIVE
    assert data["chronometer"] and data["when"] == 900
    assert [a["title"] for a in data["actions"]] == ["Stop", "Extend"]

    # Normal countdown: the phone counts down itself, no new push.
    hass.states.async_set(_entity_id("countdown"), "14", unit)
    await hass.async_block_till_done()
    assert len([c for c in notify_calls if c.data["data"].get("live_update")]) == 1

    # Extended: time jumps, so the activity is updated.
    hass.states.async_set(_entity_id("countdown"), "24", unit)
    await hass.async_block_till_done()
    assert len([c for c in notify_calls if c.data["data"].get("live_update")]) == 2

    hass.states.async_set(_entity_id("remote_start"), "off")
    await hass.async_block_till_done()
    assert LIVE in _clears(notify_calls)


async def test_extend_button(hass: HomeAssistant, ford: str) -> None:
    await _setup(hass, ford)
    press_calls = async_mock_service(hass, "button", "press")
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"FORD_ASSISTANT_EXTEND_{VIN}"}
    )
    await hass.async_block_till_done()
    assert press_calls[0].data["entity_id"] == _entity_id("extend")


async def _add_ev(hass: HomeAssistant) -> None:
    registry = er.async_get(hass)
    ford_entry = hass.config_entries.async_entries("fordpass")[0]
    device = ford_vehicle_device(hass, VIN)
    for role, key, state, attrs in (
        ("soc", "soc", "30", {"batteryRange": 60}),
        ("ev_plug", "elvehplug", "DISCONNECTED", {}),
        ("ev_charging", "elvehcharging", "NOT_READY", {}),
    ):
        registry.async_get_or_create(
            "sensor",
            "fordpass",
            f"fordpass_uid_{VIN}_{key}".lower(),
            config_entry=ford_entry,
            device_id=device.id,
            suggested_object_id=f"fordpass_{VIN.lower()}_{key}",
        )
        hass.states.async_set(_entity_id(role), state, attrs)


async def test_gas_vehicle_has_no_ev_entities(hass: HomeAssistant, ford: str) -> None:
    await _setup(hass, ford)
    assert _ours(hass, "switch", "plug_in_reminder") is None


async def test_ev_plug_in_and_charging(hass: HomeAssistant, ford: str) -> None:
    await _add_ev(hass)
    hass.states.async_set(_entity_id("tracker"), "home", {**HOME, "gps_accuracy": 5})
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    assert hass.states.get(_ours(hass, "switch", "plug_in_reminder")).state == "on"

    await entry.runtime_data._plug_in_reminder()
    assert notify_calls[-1].data["title"] == "🔌 Plug in the 2022 Escape (000001)?"
    assert notify_calls[-1].data["message"] == "Battery is at 30% (about 60 range)."

    hass.states.async_set(_entity_id("ev_plug"), "CONNECTED")
    await hass.async_block_till_done()
    assert f"ford-plugin-{VIN}" in _clears(notify_calls)

    hass.states.async_set(_entity_id("ev_charging"), "IN_PROGRESS")
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("soc"), "80", {"batteryRange": 160})
    hass.states.async_set(_entity_id("ev_charging"), "STOPPED")
    await hass.async_block_till_done()
    assert notify_calls[-1].data["title"].endswith("finished charging")
    assert notify_calls[-1].data["message"] == "Battery is at 80% (about 160 range)."

    hass.states.async_set(_entity_id("ev_charging"), "IN_PROGRESS")
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("ev_charging"), "STATION_NOT_DETECTED")
    await hass.async_block_till_done()
    assert notify_calls[-1].data["title"].endswith("charging stopped")
    assert notify_calls[-1].data["message"].startswith("The charger wasn't detected.")
    assert notify_calls[-1].data["data"]["push"] == {"interruption-level": "time-sensitive"}


BLUEPRINT_INPUTS = {
    "notify_device": ["phone1", "phone2"],
    "en_work_prompt": True,
    "work_prompt_time": "16:57:00",
    "work_prompt_days": ["tue", "wed", "thu"],
    "en_extend": True,
    "weather_entity": "weather.home",
    "todo_entity": "todo.reminders",
    "garage_cover": "cover.garage",
    "autolock_wait": {"minutes": 5},
    "garage_close_after": {"minutes": 0},
    "phone_tracker": "device_tracker.phone",
    "lock_entity": "lock.fordpass_x_doorlock",
}


def test_convert_blueprint_inputs() -> None:
    result = convert("automation.ford", "Ford", BLUEPRINT_INPUTS)
    assert result.options[CONF_NOTIFY_DEVICES] == ["phone1", "phone2"]
    assert result.options["work_prompt_days"] == ["tue", "wed", "thu"]
    assert result.options["garage_cover"] == "cover.garage"
    assert result.features == {"work_prompt": True, "auto_extend": True, "garage_close": False}
    assert result.numbers == {"auto_lock_delay": 5.0}
    assert result.times == {"work_prompt_time": "16:57:00"}


async def test_import_from_blueprint(hass: HomeAssistant, ford: str) -> None:
    inputs = {**BLUEPRINT_INPUTS, "notify_device": [ford]}
    found = [convert("automation.fordpass_vehicle_assistant", "FordPass – Vehicle Assistant", inputs)]
    turn_off = async_mock_service(hass, "automation", "turn_off")

    with patch(
        "custom_components.ford_assistant.config_flow.find_blueprint_automations",
        return_value=found,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"vin": VIN})
        assert result["step_id"] == "import_blueprint"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"automation": "automation.fordpass_vehicle_assistant", "disable_automation": True},
        )
        assert result["step_id"] == "settings"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NOTIFY_DEVICES: [ford], "home_zone": "zone.home", "garage_cover": "cover.garage"},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    entry = result["result"]
    assert entry.options["work_prompt_days"] == ["tue", "wed", "thu"]
    controller = entry.runtime_data
    assert controller.features["work_prompt"] and controller.features["auto_extend"]
    assert not controller.features["garage_close"]
    assert controller.numbers["auto_lock_delay"] == 5
    assert controller.times["work_prompt_time"].isoformat() == "16:57:00"
    assert turn_off[0].data["entity_id"] == "automation.fordpass_vehicle_assistant"


async def test_import_skip(hass: HomeAssistant, ford: str) -> None:
    found = [convert("automation.ford", "Ford", BLUEPRINT_INPUTS)]
    turn_off = async_mock_service(hass, "automation", "turn_off")
    with patch(
        "custom_components.ford_assistant.config_flow.find_blueprint_automations",
        return_value=found,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"vin": VIN})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"automation": "skip", "disable_automation": True}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NOTIFY_DEVICES: [ford], "home_zone": "zone.home"}
        )
    await hass.async_block_till_done()
    assert not turn_off
    assert not result["result"].runtime_data.features["work_prompt"]
