"""Who's driving: modes, profiles, detection, and what each mode blocks."""

from __future__ import annotations

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.ford_assistant.const import DOMAIN
from custom_components.ford_assistant.driving import (
    ACTIONS,
    ALERTS,
    GUEST_DEFAULT_ACTIONS,
    GUEST_DEFAULT_ALERTS,
    SERVICE_DEFAULT_ACTIONS,
    coerce_duration,
    matching_drivers,
    parse_duration,
    policy_for,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from .test_init import (
    AWAY,
    HOME,
    VIN,
    _entity_id,
    _ours,
    _setup,
    ford,  # noqa: F401
)

AT_HOME = {**HOME, "gps_accuracy": 5}


def test_service_and_guest_defaults() -> None:
    """Service keeps every alert and blocks every action. Guest is narrower."""
    service = policy_for("service", None, {})
    assert service.kept_alerts == ALERTS
    assert service.allowed_actions == SERVICE_DEFAULT_ACTIONS
    assert service.blocked_actions == ACTIONS
    assert service.automations_suppressed is True
    assert "oil" in service.kept_alerts
    assert "auto_lock" in service.blocked_actions
    assert "remote_start" in service.blocked_actions
    assert "garage_open" in service.blocked_actions
    assert "garage_close" in service.blocked_actions

    guest = policy_for("guest", "person.driver_one", {})
    assert guest.kept_alerts == GUEST_DEFAULT_ALERTS
    assert guest.allowed_actions == GUEST_DEFAULT_ACTIONS
    assert guest.active_driver is None  # a household driver isn't driving in Guest
    assert "alarm" in guest.kept_alerts and "charge" in guest.kept_alerts
    assert "status_activity" in guest.kept_alerts
    assert "oil" in guest.dropped_alerts
    assert "plugin" in guest.dropped_alerts
    assert "remote_start_activity" in guest.dropped_alerts
    assert set(guest.allowed_actions) == {"auto_lock", "lock", "unlock", "honk"}
    for blocked in (
        "night_lock",
        "precondition",
        "work_prompt",
        "auto_extend",
        "remote_start",
        "garage_open",
        "garage_close",
    ):
        assert blocked in guest.blocked_actions


def test_household_profile_filters_and_an_empty_list_is_a_choice() -> None:
    open_house = policy_for("household", None, {})
    assert open_house.allowed_actions == ACTIONS
    assert open_house.kept_alerts == ALERTS
    assert open_house.automations_suppressed is False
    assert open_house.notify_devices is None

    limited = policy_for(
        "household",
        "person.driver_one",
        {
            "driver_profiles": {
                "person.driver_one": {
                    "alerts": ["alarm", "not-an-alert"],
                    "actions": [],
                    "notify_devices": ["phone-1"],
                }
            }
        },
    )
    assert limited.kept_alerts == ("alarm",)
    assert limited.allowed_actions == ()
    assert limited.notify_devices == ("phone-1",)
    assert limited.automations_suppressed is True
    # No profile yet: everything, and the vehicle's phones.
    assert policy_for("household", "person.driver_one", {}).notify_devices is None


def test_matching_drivers_needs_exactly_the_departure_window() -> None:
    departure = datetime(2026, 11, 10, 15, 0)
    people = ["person.driver_one", "person.driver_two"]
    trackers = {
        "person.driver_one": ["device_tracker.driver_one"],
        "person.driver_two": (),
    }

    one = matching_drivers(
        people,
        {"person.driver_one": departure - timedelta(minutes=5)},
        trackers,
        departure,
        departure,
    )
    assert one == ["person.driver_one"]

    # The phone left even though the person entity hasn't caught up.
    by_phone = matching_drivers(
        people,
        {"device_tracker.driver_one": departure + timedelta(minutes=2)},
        trackers,
        departure,
        departure,
    )
    assert by_phone == ["person.driver_one"]

    both = matching_drivers(
        people,
        {
            "person.driver_one": departure,
            "person.driver_two": departure - timedelta(minutes=1),
        },
        trackers,
        departure,
        departure,
    )
    assert both == people

    too_early = matching_drivers(
        people,
        {"person.driver_one": departure - timedelta(minutes=20)},
        trackers,
        departure,
        departure,
    )
    assert too_early == []

    stale_trip = matching_drivers(
        people,
        {"person.driver_one": departure},
        trackers,
        departure,
        departure + timedelta(minutes=16),
    )
    assert stale_trip == []


def test_durations() -> None:
    assert parse_duration("01:30:00") == timedelta(hours=1, minutes=30)
    assert parse_duration({"hours": 2, "minutes": 15}) == timedelta(hours=2, minutes=15)
    assert parse_duration(0) == timedelta(0)
    assert coerce_duration({"hours": 2}) == timedelta(hours=2)
    assert coerce_duration(0) is None
    assert coerce_duration(None) is None
    assert coerce_duration("nope") is None
    with pytest.raises(ValueError):
        parse_duration(-5)


async def _mode(hass: HomeAssistant, mode: str, **fields) -> None:
    await hass.services.async_call(
        DOMAIN,
        "set_driving_mode",
        {"entity_id": _ours(hass, "select", "driving_mode"), "mode": mode, **fields},
        blocking=True,
    )


async def test_entities_start_in_household(hass: HomeAssistant, ford: str) -> None:
    await _setup(hass, ford)
    assert hass.states.get(_ours(hass, "select", "driving_mode")).state == "household"
    assert hass.states.get(_ours(hass, "select", "active_driver")).state == "none"
    assert hass.states.get(_ours(hass, "sensor", "driving_status")).state == "household"
    sensor = hass.states.get(_ours(hass, "sensor", "driving_status"))
    assert sensor.attributes["blocked_actions"] == []
    assert sensor.attributes["automations_suppressed"] is False
    assert (
        hass.states.get(_ours(hass, "binary_sensor", "automations_suppressed")).state
        == "off"
    )


async def test_service_mode_holds_the_lock_and_remote_start(
    hass: HomeAssistant, ford: str
) -> None:
    from homeassistant.util import dt as dt_util

    lock_calls = async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    press_calls = async_mock_service(hass, "button", "press")
    events = async_capture_events(hass, "ford_assistant_driving_mode_changed")
    entry = await _setup(hass, ford)
    await _mode(hass, "service")
    assert hass.states.get(_ours(hass, "select", "driving_mode")).state == "service"
    assert (
        hass.states.get(_ours(hass, "binary_sensor", "automations_suppressed")).state
        == "on"
    )
    assert events[-1].data["mode"] == "service"
    assert events[-1].data["previous_mode"] == "household"
    assert events[-1].data["vin"] == VIN
    assert "auto_lock" in events[-1].data["blocked_actions"]
    assert "alarm" in events[-1].data["kept_alerts"]

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=4))
    await hass.async_block_till_done()
    assert lock_calls == []

    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"FORD_ASSISTANT_START_{VIN}"}
    )
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"FORD_ASSISTANT_LOCK_{VIN}"}
    )
    await hass.async_block_till_done()
    assert lock_calls == []

    # Asking the vehicle for a fresh status is not one of the blocked actions.
    hass.states.async_set(_entity_id("doors"), "Open")
    await entry.runtime_data._door_recheck()
    assert any(call.data["entity_id"] == _entity_id("refresh") for call in press_calls)

    hass.states.async_set(_entity_id("fuel"), "12", {"fuelRange": 40})
    await hass.async_block_till_done()
    fuel = [call for call in notify_calls if "fuel" in call.data["title"].lower()]
    assert len(fuel) == 1

    entry.runtime_data.set_feature("auto_extend", True)
    hass.states.async_set(_entity_id("remote_start"), "on")
    hass.states.async_set(_entity_id("countdown"), "1", {"unit_of_measurement": "min"})
    await hass.async_block_till_done()
    assert not any(
        call.data["entity_id"] == _entity_id("extend") for call in press_calls
    )


async def test_guest_mode_blocks_the_garage_and_drops_oil(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    opens = async_mock_service(hass, "cover", "open_cover")
    lock_calls = async_mock_service(hass, "lock", "lock")
    notify_calls = async_mock_service(hass, "notify", "mobile_app_my_phone")
    entry = await _setup(hass, ford)
    hass.states.async_set("cover.garage", "closed")
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "garage_cover": "cover.garage"}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await _mode(hass, "guest")

    hass.states.async_set(_entity_id("ignition"), "RUN")
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("tracker"), "not_home", AWAY)
    hass.states.async_set(_entity_id("tracker"), "home", AT_HOME)
    await hass.async_block_till_done()
    assert opens == []

    hass.states.async_set(_entity_id("alarm"), "TRIGGERED")
    await hass.async_block_till_done()
    assert any("alarm" in call.data["title"].lower() for call in notify_calls)

    before = len(notify_calls)
    hass.states.async_set(_entity_id("oil"), "4")
    await hass.async_block_till_done()
    assert len(notify_calls) == before

    await _mode(hass, "household")
    oil = [call for call in notify_calls if "oil" in call.data["title"].lower()]
    assert len(oil) == 1

    # Auto-lock is allowed for a guest, once the car is away again.
    hass.states.async_set(_entity_id("ignition"), "OFF")
    hass.states.async_set(_entity_id("tracker"), "not_home", AWAY)
    hass.states.async_set(_entity_id("lock"), "unlocked")
    await _mode(hass, "guest")
    freezer.tick(timedelta(minutes=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert lock_calls


async def test_mode_persists_and_reverts_after_a_restart(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass, ford)
    events = async_capture_events(hass, "ford_assistant_driving_mode_changed")
    await _mode(hass, "service", duration={"minutes": 30})
    revert_at = entry.runtime_data._revert_at
    assert revert_at is not None
    assert hass.states.get(_ours(hass, "sensor", "driving_status")).attributes[
        "revert_at"
    ]

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.driving_mode == "service"
    assert entry.runtime_data._revert_at == revert_at

    freezer.tick(timedelta(minutes=30, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entry.runtime_data.driving_mode == "household"
    assert entry.runtime_data._revert_at is None
    assert events[-1].data["reason"] == "revert"
    assert (
        hass.states.get(_ours(hass, "binary_sensor", "automations_suppressed")).state
        == "off"
    )


async def test_zero_duration_does_not_revert(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass, ford)
    await _mode(hass, "guest", duration=0)
    assert entry.runtime_data._revert_at is None
    freezer.tick(timedelta(days=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entry.runtime_data.driving_mode == "guest"


async def test_options_cover_drivers_profiles_and_both_modes(
    hass: HomeAssistant, ford: str
) -> None:
    hass.states.async_set("person.driver_one", "home", {"friendly_name": "Driver One"})
    hass.states.async_set("person.driver_two", "home", {"friendly_name": "Driver Two"})
    entry = await _setup(hass, ford)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "household_drivers"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"household_drivers": ["person.driver_one", "person.driver_two"]},
    )
    assert result["step_id"] == "driver_profile"
    assert result["description_placeholders"]["person"] == "Driver One"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "alerts": ["alarm", "door"],
            "notify_devices": [ford],
            "actions": ["lock", "honk"],
        },
    )
    assert result["step_id"] == "driver_profile"
    assert result["description_placeholders"]["person"] == "Driver Two"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"alerts": list(ALERTS), "notify_devices": [], "actions": list(ACTIONS)},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["household_drivers"] == [
        "person.driver_one",
        "person.driver_two",
    ]
    assert entry.options["driver_profiles"]["person.driver_one"]["alerts"] == [
        "alarm",
        "door",
    ]
    assert entry.options["driver_profiles"]["person.driver_one"]["notify_devices"] == [
        ford
    ]

    select = hass.states.get(_ours(hass, "select", "active_driver"))
    # Shown by name (1.8.1); the person entity is an attribute.
    assert select.attributes["options"] == ["none", "Driver One", "Driver Two"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "service_mode"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "service_alerts": ["alarm", "battery"],
            "service_actions": ["honk"],
            "service_revert": {"hours": 4},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    # Saving Service mode must not drop the drivers.
    assert "person.driver_one" in entry.options["household_drivers"]
    assert entry.options["service_actions"] == ["honk"]
    assert entry.options["service_revert"] == {"hours": 4}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "guest_mode"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "guest_alerts": ["alarm"],
            "guest_actions": ["lock"],
            "guest_revert": {"minutes": 45},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    await _mode(hass, "service")
    policy = entry.runtime_data.policy
    assert policy.kept_alerts == ("alarm", "battery")
    assert policy.allowed_actions == ("honk",)
    assert entry.runtime_data._revert_at is not None

    # Phones and places still save, and still keep the driving options.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "notify_devices": [ford],
            "home_zone": "zone.home",
            "precondition_days": ["sat"],
            "work_prompt_days": ["sun"],
            "alarm_normal_states": ["DISARMED"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["household_drivers"]
    assert entry.options["service_actions"] == ["honk"]
    assert entry.options["precondition_days"] == ["sat"]


async def test_driver_profile_limits_alerts_phones_and_actions(
    hass: HomeAssistant, ford: str
) -> None:
    from homeassistant.helpers import device_registry as dr

    other_entry_id = "other-phone"
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    phone_entry = MockConfigEntry(
        domain="mobile_app",
        data={"device_name": "Other Phone"},
        entry_id=other_entry_id,
    )
    phone_entry.add_to_hass(hass)
    other = dr.async_get(hass).async_get_or_create(
        config_entry_id=phone_entry.entry_id,
        identifiers={("mobile_app", "other")},
    )
    hass.states.async_set("person.driver_one", "home", {"friendly_name": "Driver One"})
    entry = await _setup(hass, ford)
    mine = async_mock_service(hass, "notify", "mobile_app_my_phone")
    theirs = async_mock_service(hass, "notify", "mobile_app_other_phone")
    lock_calls = async_mock_service(hass, "lock", "lock")
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "household_drivers": ["person.driver_one"],
            "driver_profiles": {
                "person.driver_one": {
                    "alerts": ["alarm"],
                    "notify_devices": [other.id],
                    "actions": ["lock"],
                }
            },
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": _ours(hass, "select", "active_driver"),
            "option": "Driver One",
        },
        blocking=True,
    )
    assert entry.runtime_data.active_driver_manual is True
    assert (
        hass.states.get(_ours(hass, "binary_sensor", "automations_suppressed")).state
        == "on"
    )

    hass.states.async_set(_entity_id("fuel"), "8", {"fuelRange": 20})
    await hass.async_block_till_done()
    assert mine == [] and theirs == []

    hass.states.async_set(_entity_id("alarm"), "TRIGGERED")
    await hass.async_block_till_done()
    assert mine == []
    assert len(theirs) == 1
    assert "alarm" in theirs[0].data["title"].lower()

    from homeassistant.util import dt as dt_util

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=4))
    await hass.async_block_till_done()
    assert lock_calls == []

    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"FORD_ASSISTANT_LOCK_{VIN}"}
    )
    await hass.async_block_till_done()
    assert len(lock_calls) == 1


async def test_departure_names_one_driver_and_parking_clears_them(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set(
        "person.driver_one",
        "home",
        {
            "friendly_name": "Driver One",
            "device_trackers": ["device_tracker.driver_one"],
        },
    )
    hass.states.async_set("device_tracker.driver_one", "home")
    hass.states.async_set(_entity_id("tracker"), "home", AT_HOME)
    entry = await _setup(hass, ford)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "household_drivers": ["person.driver_one"]}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "person.driver_one",
        "not_home",
        {
            "friendly_name": "Driver One",
            "device_trackers": ["device_tracker.driver_one"],
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("tracker"), "not_home", AWAY)
    await hass.async_block_till_done()
    assert entry.runtime_data.active_driver == "person.driver_one"
    assert (
        hass.states.get(_ours(hass, "sensor", "driving_status")).attributes[
            "active_driver_name"
        ]
        == "Driver One"
    )

    # Coming home during the startup wait does not forget the trip.
    hass.states.async_set(_entity_id("tracker"), "home", AT_HOME)
    await hass.async_block_till_done()
    assert entry.runtime_data.active_driver == "person.driver_one"

    freezer.tick(timedelta(minutes=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("tracker"), "not_home", AWAY)
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("tracker"), "home", AT_HOME)
    await hass.async_block_till_done()
    assert entry.runtime_data.active_driver is None
    assert hass.states.get(_ours(hass, "select", "active_driver")).state == "none"


async def test_two_people_leaving_is_not_a_guess(
    hass: HomeAssistant, ford: str
) -> None:
    for name in ("driver_one", "driver_two"):
        hass.states.async_set(f"person.{name}", "home", {"friendly_name": name})
    hass.states.async_set(_entity_id("tracker"), "home", AT_HOME)
    entry = await _setup(hass, ford)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "household_drivers": ["person.driver_one", "person.driver_two"],
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_set("person.driver_one", "not_home")
    hass.states.async_set("person.driver_two", "not_home")
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("tracker"), "not_home", AWAY)
    await hass.async_block_till_done()
    assert entry.runtime_data.active_driver is None


async def test_a_manual_driver_is_not_replaced(hass: HomeAssistant, ford: str) -> None:
    hass.states.async_set("person.driver_one", "home", {"friendly_name": "Driver One"})
    hass.states.async_set("person.driver_two", "home", {"friendly_name": "Driver Two"})
    hass.states.async_set(_entity_id("tracker"), "home", AT_HOME)
    entry = await _setup(hass, ford)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "household_drivers": ["person.driver_one", "person.driver_two"],
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": _ours(hass, "select", "active_driver"),
            "option": "Driver Two",
        },
        blocking=True,
    )
    select = hass.states.get(_ours(hass, "select", "active_driver"))
    assert select.state == "Driver Two"
    assert select.attributes["person"] == "person.driver_two"
    hass.states.async_set("person.driver_one", "not_home")
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("tracker"), "not_home", AWAY)
    await hass.async_block_till_done()
    assert entry.runtime_data.active_driver == "person.driver_two"
    assert entry.runtime_data.active_driver_manual is True


async def test_a_phone_leaving_home_counts(hass: HomeAssistant, ford: str) -> None:
    hass.states.async_set(
        "person.driver_one",
        "home",
        {
            "friendly_name": "Driver One",
            "device_trackers": ["device_tracker.driver_one"],
        },
    )
    hass.states.async_set("device_tracker.driver_one", "home")
    hass.states.async_set(_entity_id("tracker"), "home", AT_HOME)
    entry = await _setup(hass, ford)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "household_drivers": ["person.driver_one"]}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    # The person entity is still home; their phone has left.
    hass.states.async_set("device_tracker.driver_one", "not_home")
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("tracker"), "not_home", AWAY)
    await hass.async_block_till_done()
    assert entry.runtime_data.active_driver == "person.driver_one"


async def test_unknown_driver_is_rejected(hass: HomeAssistant, ford: str) -> None:
    hass.states.async_set("person.driver_one", "home", {"friendly_name": "Driver One"})
    entry = await _setup(hass, ford)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "household_drivers": ["person.driver_one"]}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(HomeAssistantError) as err:
        await _mode(hass, "household", active_driver="person.someone_else")
    assert err.value.translation_key == "unknown_driver"
    assert entry.runtime_data.active_driver is None


async def test_household_driver_can_open_the_dashboard(
    hass: HomeAssistant, ford: str, hass_ws_client, hass_admin_user
) -> None:
    from pytest_homeassistant_custom_component.common import CLIENT_ID

    entry = await _setup(hass, ford)
    driver = await hass.auth.async_create_user("Driver", group_ids=["system-users"])
    stranger = await hass.auth.async_create_user("Stranger", group_ids=["system-users"])
    hass.states.async_set(
        "person.driver_one",
        "home",
        {"friendly_name": "Driver One", "user_id": driver.id},
    )
    hass.states.async_set("person.no_login", "home", {"friendly_name": "No Login"})
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "household_drivers": ["person.driver_one", "person.no_login"],
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    async def allowed(user) -> bool:
        token = hass.auth.async_create_access_token(
            await hass.auth.async_create_refresh_token(user, CLIENT_ID)
        )
        client = await hass_ws_client(hass, token)
        await client.send_json_auto_id({"type": "ford_assistant/access/me"})
        me = await client.receive_json()
        return me["result"]["allowed"]

    assert await allowed(driver) is True
    assert await allowed(stranger) is False


async def test_precondition_does_not_start_in_service_mode(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    # A Wednesday: preconditioning only runs on its days (weekdays by default).
    freezer.move_to("2026-11-11 15:00:00+00:00")
    entry = await _setup(hass, ford)
    starts = async_mock_service(hass, "switch", "turn_on")
    entry.runtime_data.set_feature("precondition", True)
    hass.states.async_set(_entity_id("tracker"), "home", AT_HOME)
    await entry.runtime_data._precondition()
    assert len(starts) == 1
    await _mode(hass, "service")
    await entry.runtime_data._precondition()
    assert len(starts) == 1


def test_driver_labels_are_names_and_unique() -> None:
    """1.8.1: the list shows names; two people with one name stay apart."""
    from types import SimpleNamespace

    from custom_components.ford_assistant.select import ActiveDriverSelect

    states = {
        "person.a": SimpleNamespace(name="Alex"),
        "person.b": SimpleNamespace(name="Alex"),
        "person.c": SimpleNamespace(name="none"),
    }
    select = ActiveDriverSelect.__new__(ActiveDriverSelect)
    select.hass = SimpleNamespace(states=SimpleNamespace(get=states.get))
    select.controller = SimpleNamespace(
        household_drivers=["person.a", "person.b", "person.c", "person.d"]
    )
    assert select._labels() == {  # noqa: SLF001
        "Alex": "person.a",
        "Alex (2)": "person.b",
        "none (2)": "person.c",
        "person.d": "person.d",
    }
