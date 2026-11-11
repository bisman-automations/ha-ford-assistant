"""FordPass China support: discovery, setup, and the bridge entities."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.ford_assistant.const import (
    CONF_NOTIFY_DEVICES,
    CONF_SOURCE,
    DOMAIN,
)
from custom_components.ford_assistant.discovery import ford_vehicles, resolve_entities
from custom_components.ford_assistant.sources import CN_KEYS, SOURCE_CHINA
from homeassistant import config_entries
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

TOKEN = "a1b2c3d4e5f60718"
HOME = {"latitude": 40.84, "longitude": 111.75, "radius": 100}

CN_STATES = {
    "lock_status": ("已锁定", {}),
    "ignition": ("已熄火", {}),
    "driver_door": ("已关闭", {}),
    "passenger_door": ("已关闭", {}),
    "left_rear_door": ("已关闭", {}),
    "right_rear_door": ("已关闭", {}),
    "tailgate": ("已关闭", {}),
    "hood": ("已关闭", {}),
    "driver_window": ("已关闭", {}),
    "passenger_window": ("已关闭", {}),
    "left_rear_window": ("已关闭", {}),
    "right_rear_window": ("已关闭", {}),
    "lf_tire": ("235", {"unit_of_measurement": "kPa"}),
    "rf_tire": ("236", {"unit_of_measurement": "kPa"}),
    "lr_tire": ("234", {"unit_of_measurement": "kPa"}),
    "rr_tire": ("235", {"unit_of_measurement": "kPa"}),
    "lf_tire_status": ("正常", {}),
    "rf_tire_status": ("正常", {}),
    "lr_tire_status": ("正常", {}),
    "rr_tire_status": ("正常", {}),
    "alarm_status": ("车辆已设防", {}),
    "fuel_level": ("55", {"unit_of_measurement": "%"}),
    "distance_to_empty": ("320", {"unit_of_measurement": "km"}),
    "odometer": ("12345", {"unit_of_measurement": "km"}),
    "prognostic": ("72", {"unit_of_measurement": "%"}),
    "auto_off_remaining": ("0", {"unit_of_measurement": "min"}),
    "remote_start": ("未远程启动", {}),
    "engine": ("off", {}),
    "honk": ("off", {}),
    "manual_refresh": ("unknown", {}),
    "tracker": ("home", {**HOME, "gps_accuracy": 5}),
    "lock_door": ("unknown", {}),
    "unlock_door": ("unknown", {}),
    "vehicle_image": ("unknown", {}),
}


def _cn_entity(key: str) -> str:
    """The state entity id this fixture gave a FordPass China reading."""
    return f"{CN_KEYS[key]}.fordpass_cn_{key}".lower()


@pytest.fixture
async def china(hass: HomeAssistant) -> str:
    """Pretend the FordPass China integration set up a car and a phone."""
    hass.states.async_set("zone.home", "0", HOME)
    cn_entry = MockConfigEntry(domain=SOURCE_CHINA)
    cn_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=cn_entry.entry_id,
        identifiers={(SOURCE_CHINA, TOKEN)},
        name="2022 Mondeo",
        model="2022 Mondeo",
    )
    registry = er.async_get(hass)
    for key, (state, attributes) in CN_STATES.items():
        registry.async_get_or_create(
            CN_KEYS[key],
            SOURCE_CHINA,
            f"{TOKEN}-{key}".lower(),
            config_entry=cn_entry,
            device_id=device.id,
            suggested_object_id=f"fordpass_cn_{key}",
        )
        hass.states.async_set(_cn_entity(key), state, attributes)

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
        result["flow_id"], {"vin": TOKEN}
    )
    assert result["step_id"] == "settings"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NOTIFY_DEVICES: [phone_id], "home_zone": "zone.home"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def test_china_vehicle_offered(hass: HomeAssistant, china: str) -> None:
    vehicles = ford_vehicles(hass)
    assert list(vehicles) == [TOKEN]
    assert vehicles[TOKEN].source == SOURCE_CHINA
    assert vehicles[TOKEN].name == "2022 Mondeo (f60718)"


async def test_china_entry_gets_bridge_entities(
    hass: HomeAssistant, china: str
) -> None:
    entry = await _setup(hass, china)
    assert entry.data[CONF_SOURCE] == SOURCE_CHINA
    entities = resolve_entities(hass, TOKEN, SOURCE_CHINA)
    assert entry.runtime_data.entities == entities
    # Everything Ford Assistant insists on exists, including the bridge lock.
    assert {"lock", "tracker", "doors", "windows", "tires"} <= set(entities)
    # No EV readings for this car, so no EV bridges or roles.
    assert "soc" not in entities
    assert "ev_plug" not in entities
    assert not entry.runtime_data.is_electric


async def test_china_bridge_readings(hass: HomeAssistant, china: str) -> None:
    await _setup(hass, china)
    entities = resolve_entities(hass, TOKEN, SOURCE_CHINA)

    assert hass.states.get(entities["lock"]).state == "locked"
    assert hass.states.get(entities["ignition"]).state == "OFF"
    assert hass.states.get(entities["doors"]).state == "Closed"
    assert hass.states.get(entities["windows"]).state == "Closed"
    assert hass.states.get(entities["alarm"]).state == "ARMED"
    assert hass.states.get(entities["tires"]).state == "NORMAL_OPERATION"
    assert hass.states.get(entities["fuel"]).state == "55"
    assert hass.states.get(entities["fuel"]).attributes["fuelRange"] == 320

    # A door opening flows through to the aggregate and its attributes.
    hass.states.async_set(_cn_entity("driver_door"), "已打开")
    await hass.async_block_till_done()
    doors = hass.states.get(entities["doors"])
    assert doors.state == "Open"
    assert doors.attributes["driverFront"] == "OPEN"

    # A low tire turns the aggregate into a warning.
    hass.states.async_set(_cn_entity("lf_tire_status"), "故障")
    await hass.async_block_till_done()
    tires = hass.states.get(entities["tires"])
    assert tires.state == "WARNING"
    assert tires.attributes["frontLeft_state"] == "FAULT"


async def test_china_lock_uses_the_action_buttons(
    hass: HomeAssistant, china: str
) -> None:
    await _setup(hass, china)
    entities = resolve_entities(hass, TOKEN, SOURCE_CHINA)
    press = async_mock_service(hass, "button", "press")

    await hass.services.async_call(
        "lock", "unlock", {"entity_id": entities["lock"]}, blocking=True
    )
    assert press[-1].data["entity_id"] == _cn_entity("unlock_door")

    await hass.services.async_call(
        "lock", "lock", {"entity_id": entities["lock"]}, blocking=True
    )
    assert press[-1].data["entity_id"] == _cn_entity("lock_door")


async def test_china_remote_start_and_honk(hass: HomeAssistant, china: str) -> None:
    await _setup(hass, china)
    entities = resolve_entities(hass, TOKEN, SOURCE_CHINA)
    calls: list[str] = []

    @callback
    def _record(event) -> None:
        data = event.data
        if entity_id := data.get("service_data", {}).get("entity_id"):
            calls.append(entity_id)

    hass.bus.async_listen("call_service", _record)

    # The bridge switch calls the FordPass China engine switch.
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entities["remote_start"]}, blocking=True
    )
    await hass.async_block_till_done()
    assert calls == [entities["remote_start"], _cn_entity("engine")]

    # The bridge button honks through the FordPass China honk switch.
    await hass.services.async_call(
        "button", "press", {"entity_id": entities["honk"]}, blocking=True
    )
    await hass.async_block_till_done()
    assert calls[-1] == _cn_entity("honk")


def _select(hass: HomeAssistant, key: str) -> str:
    """The one select entity for that role on the bridge vehicle."""
    return next(
        entity_id
        for entity_id in hass.states.async_entity_ids("select")
        if key in entity_id
    )


async def test_china_service_mode_blocks_its_actions(
    hass: HomeAssistant, china: str
) -> None:
    calls: list[str] = []

    @callback
    def _record(event) -> None:
        data = event.data
        if entity_id := data.get("service_data", {}).get("entity_id"):
            calls.append(entity_id)

    await _setup(hass, china)
    hass.bus.async_listen("call_service", _record)
    entities = resolve_entities(hass, TOKEN, SOURCE_CHINA)
    await hass.services.async_call(
        DOMAIN,
        "set_driving_mode",
        {"entity_id": _select(hass, "who_s_driving"), "mode": "service"},
        blocking=True,
    )

    for domain, service, key in (
        ("lock", "unlock", "lock"),
        ("switch", "turn_on", "remote_start"),
        ("button", "press", "honk"),
    ):
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                domain,
                service,
                {"entity_id": entities[key]},
                blocking=True,
            )
        assert err.value.translation_key == "action_blocked"

    await hass.async_block_till_done()
    assert _cn_entity("unlock_door") not in calls
    assert _cn_entity("engine") not in calls
    assert _cn_entity("honk") not in calls


async def test_china_actions_need_access(
    hass: HomeAssistant, china: str, hass_admin_user
) -> None:
    await _setup(hass, china)
    entities = resolve_entities(hass, TOKEN, SOURCE_CHINA)
    kid = await hass.auth.async_create_user("Kid", group_ids=["system-users"])
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "lock",
            "lock",
            {"entity_id": entities["lock"]},
            blocking=True,
            context=Context(user_id=kid.id),
        )
    assert err.value.translation_key == "not_allowed"


async def test_china_alarm_alert(hass: HomeAssistant, china: str) -> None:
    notify = async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, china)
    entities = resolve_entities(hass, TOKEN, SOURCE_CHINA)

    hass.states.async_set(_cn_entity("alarm_status"), "被盗声光报警中")
    await hass.async_block_till_done()
    assert hass.states.get(entities["alarm"]).state == "ALARM"
    assert any("alarm" in call.data["title"].lower() for call in notify)
