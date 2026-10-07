"""Integration tests for Ford Assistant."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.ford_assistant.const import (
    CONF_NOTIFY_DEVICES,
    DOMAIN,
    FORD_ENTITY_KEYS,
)

VIN = "1FTEST00000000001"
HOME = {"latitude": 46.8, "longitude": -100.78, "radius": 100}
AWAY = {"latitude": 46.9, "longitude": -100.9, "gps_accuracy": 10}

STATES = {
    "lock": ("unlocked", {}),
    "tracker": ("not_home", AWAY),
    "ignition": ("OFF", {}),
    "doors": ("Closed", {}),
    "windows": ("Closed", {}),
    "remote_start": ("off", {}),
    "countdown": ("0", {"unit_of_measurement": "min"}),
    "extend": ("unknown", {}),
    "honk": ("unknown", {}),
    "alarm": ("DISARMED", {}),
    "fuel": ("50", {"fuelRange": 200}),
    "oil": ("80", {}),
    "battery": ("90", {}),
    "tires": ("NORMAL_OPERATION", {}),
    "indicators": ("0", {}),
    "temperature": ("20", {}),
}


def _entity_id(role: str) -> str:
    platform, key = FORD_ENTITY_KEYS[role]
    return f"{platform}.fordpass_{VIN.lower()}_{key}"


@pytest.fixture
async def ford(hass: HomeAssistant) -> str:
    """Pretend the Ford integration set up a vehicle and a phone."""
    hass.states.async_set("zone.home", "0", HOME)
    ford_entry = MockConfigEntry(domain="fordpass")
    ford_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=ford_entry.entry_id,
        identifiers={("fordpass", VIN)},
        name=f"VIN: {VIN}",
        model="2022 Escape",
    )
    registry = er.async_get(hass)
    for role, (platform, key) in FORD_ENTITY_KEYS.items():
        registry.async_get_or_create(
            platform,
            "fordpass",
            f"fordpass_uid_{VIN}_{key}".lower(),
            config_entry=ford_entry,
            device_id=device.id,
            suggested_object_id=f"fordpass_{VIN.lower()}_{key}",
        )
        state, attrs = STATES[role]
        hass.states.async_set(_entity_id(role), state, attrs)

    phone_entry = MockConfigEntry(domain="mobile_app", data={"device_name": "My Phone"})
    phone_entry.add_to_hass(hass)
    phone = dr.async_get(hass).async_get_or_create(
        config_entry_id=phone_entry.entry_id, identifiers={("mobile_app", "phone")}
    )
    return phone.id


async def _setup(hass: HomeAssistant, phone_id: str) -> MockConfigEntry:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vin": VIN}
    )
    assert result["step_id"] == "settings"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NOTIFY_DEVICES: [phone_id], "home_zone": "zone.home"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "2022 Escape (000001)"
    await hass.async_block_till_done()
    return result["result"]


async def test_no_vehicles(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_vehicles"


async def test_entities_join_ford_device(hass: HomeAssistant, ford: str) -> None:
    lock_calls = async_mock_service(hass, "lock", "lock")
    entry = await _setup(hass, ford)
    device = dr.async_get(hass).async_get_device(identifiers={("fordpass", VIN)})
    ours = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert ours and all(e.device_id == device.id for e in ours)
    assert hass.states.get("switch.vin_1ftest00000000001_auto_lock_away_from_home").state == "on"
    assert not lock_calls


async def test_auto_lock_and_notify(hass: HomeAssistant, ford: str) -> None:
    lock_calls = async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=4))
    await hass.async_block_till_done()

    assert len(lock_calls) == 1
    assert lock_calls[0].data["entity_id"] == _entity_id("lock")
    assert len(notify_calls) == 1
    actions = notify_calls[0].data["data"]["actions"]
    assert actions[0]["action"] == f"FORD_ASSISTANT_HONK_{VIN}"


async def test_no_auto_lock_at_home(hass: HomeAssistant, ford: str) -> None:
    hass.states.async_set(_entity_id("tracker"), "home", {**HOME, "gps_accuracy": 5})
    lock_calls = async_mock_service(hass, "lock", "lock")
    await _setup(hass, ford)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=4))
    await hass.async_block_till_done()
    assert not lock_calls


async def test_notification_button_starts(hass: HomeAssistant, ford: str) -> None:
    await _setup(hass, ford)
    # Mock after setup: loading our switch platform registers the real service.
    start_calls = async_mock_service(hass, "switch", "turn_on")
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"FORD_ASSISTANT_START_{VIN}"}
    )
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": "FORD_ASSISTANT_START_OTHERVIN"}
    )
    await hass.async_block_till_done()
    assert len(start_calls) == 1
    assert start_calls[0].data["entity_id"] == _entity_id("remote_start")


async def test_low_fuel_alerts_once(hass: HomeAssistant, ford: str) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    events = []
    hass.bus.async_listen("ford_assistant_alert", events.append)
    await _setup(hass, ford)

    for level in ("12", "11", "10"):
        hass.states.async_set(_entity_id("fuel"), level, {"fuelRange": 40})
        await hass.async_block_till_done()

    fuel_notes = [c for c in notify_calls if "fuel" in c.data["title"]]
    assert len(fuel_notes) == 1
    assert fuel_notes[0].data["message"] == "12% left (about 40 range)."
    assert [e.data["type"] for e in events] == ["fuel"]


async def test_auto_extend(hass: HomeAssistant, ford: str) -> None:
    press_calls = async_mock_service(hass, "button", "press")
    entry = await _setup(hass, ford)
    entry.runtime_data.set_feature("auto_extend", True)
    hass.states.async_set(_entity_id("remote_start"), "on")
    for minutes in ("10", "5", "1.5", "1"):
        hass.states.async_set(_entity_id("countdown"), minutes, {"unit_of_measurement": "min"})
        await hass.async_block_till_done()
    assert len(press_calls) == 1
    assert press_calls[0].data["entity_id"] == _entity_id("extend")


async def test_settings_persist(hass: HomeAssistant, ford: str) -> None:
    entry = await _setup(hass, ford)
    entry.runtime_data.set_number("fuel_threshold", 25)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.numbers["fuel_threshold"] == 25


async def test_options_flow(hass: HomeAssistant, ford: str) -> None:
    entry = await _setup(hass, ford)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_NOTIFY_DEVICES: [ford],
            "home_zone": "zone.home",
            "precondition_days": ["sat", "sun"],
            "work_prompt_days": ["tue", "wed", "thu"],
            "alarm_normal_states": ["ARMED", "DISARMED"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["work_prompt_days"] == ["tue", "wed", "thu"]
    assert entry.runtime_data.options["precondition_days"] == ["sat", "sun"]


def _clears(calls) -> list[str]:
    return [c.data["data"]["tag"] for c in calls if c.data["message"] == "clear_notification"]


async def test_night_lock(hass: HomeAssistant, ford: str) -> None:
    hass.states.async_set(_entity_id("tracker"), "home", {**HOME, "gps_accuracy": 5})
    lock_calls = async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    await entry.runtime_data._night_lock()
    await hass.async_block_till_done()
    assert len(lock_calls) == 1
    assert notify_calls[-1].data["title"].endswith("locked for the night")


async def test_night_lock_door_open(hass: HomeAssistant, ford: str) -> None:
    hass.states.async_set(_entity_id("tracker"), "home", {**HOME, "gps_accuracy": 5})
    hass.states.async_set(_entity_id("doors"), "Open", {"rearLeft": "OPEN", "hood": "OPEN"})
    lock_calls = async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    await entry.runtime_data._night_lock()
    await hass.async_block_till_done()
    assert not lock_calls
    assert notify_calls[-1].data["message"] == "Rear left and hood are open."


async def test_door_open_alert_and_clear(hass: HomeAssistant, ford: str) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)

    hass.states.async_set(_entity_id("doors"), "Open", {"driverFront": "OPEN", "hood": "CLOSED"})
    await hass.async_block_till_done()
    for minutes in (11, 22):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=minutes))
        await hass.async_block_till_done()

    door = [c for c in notify_calls if c.data.get("title", "").startswith("🚪")]
    assert len(door) == 1
    assert door[0].data["message"] == "Driver front has been open for 10 minutes."

    hass.states.async_set(_entity_id("doors"), "Closed", {})
    await hass.async_block_till_done()
    assert _clears(notify_calls) == [f"ford-door-{VIN}"]


async def test_fuel_alert_clears_on_refuel(hass: HomeAssistant, ford: str) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)
    hass.states.async_set(_entity_id("fuel"), "10", {})
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("fuel"), "90", {})
    await hass.async_block_till_done()
    assert _clears(notify_calls) == [f"ford-fuel-{VIN}"]


async def test_start_prompt_clears(hass: HomeAssistant, ford: str) -> None:
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    await entry.runtime_data._notify("start", "Start?", "Tap Start", actions=["START"])
    hass.states.async_set(_entity_id("remote_start"), "on")
    await hass.async_block_till_done()
    assert not _clears(notify_calls)
    hass.states.async_set(_entity_id("remote_start"), "off")
    await hass.async_block_till_done()
    assert _clears(notify_calls) == [f"ford-start-{VIN}"]


async def test_clearing_can_be_turned_off(hass: HomeAssistant, ford: str) -> None:
    async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    entry.runtime_data.set_feature("clear_resolved", False)
    hass.states.async_set(_entity_id("fuel"), "10", {})
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("fuel"), "90", {})
    await hass.async_block_till_done()
    assert not _clears(notify_calls)
