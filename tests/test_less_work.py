"""1.8.4: writes that change nothing, the auto-lock wait, and diagnostics."""

from __future__ import annotations

from datetime import timedelta

from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.ford_assistant.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import EVENT_STATE_CHANGED, EVENT_STATE_REPORTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .test_china import _cn_entity, _setup as _setup_china, china  # noqa: F401
from .test_init import _entity_id, _ours, _setup, ford  # noqa: F401


def _record_writes(
    hass: HomeAssistant, entity_ids: set[str]
) -> tuple[list[str], list[str]]:
    """Entity ids written with a change, and written again unchanged."""
    changed: list[str] = []
    reported: list[str] = []

    @callback
    def _ours(event_data) -> bool:
        return event_data["entity_id"] in entity_ids

    hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        callback(lambda event: changed.append(event.data["entity_id"])),
        event_filter=_ours,
    )
    hass.bus.async_listen(
        EVENT_STATE_REPORTED,
        callback(lambda event: reported.append(event.data["entity_id"])),
        event_filter=_ours,
    )
    return changed, reported


async def test_entities_written_only_when_changed(
    hass: HomeAssistant, ford: str
) -> None:
    entry = await _setup(hass, ford)
    controller = entry.runtime_data
    ours = {
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }
    assert len(ours) > 10
    controller.set_number("fuel_threshold", 14)  # each entity's first update writes
    await hass.async_block_till_done()
    changed, reported = _record_writes(hass, ours)

    controller.set_number("fuel_threshold", 13)
    await hass.async_block_till_done()

    assert changed == [_ours(hass, "number", "fuel_threshold")]
    assert reported == []  # nobody else was written again unchanged

    # Something else writing the entity (a rename, Home Assistant itself) is
    # written over on the next update, even though our value didn't change.
    number = _ours(hass, "number", "fuel_threshold")
    hass.states.async_set(number, "99")
    controller.set_feature("auto_lock", True)
    await hass.async_block_till_done()
    assert hass.states.get(number).state == "13"


async def test_bridge_skips_updates_that_change_nothing(
    hass: HomeAssistant,
    china: str,  # noqa: F811
) -> None:
    entry = await _setup_china(hass, china)
    lock = entry.runtime_data.entities["lock"]
    hass.states.async_set(_cn_entity("unlock_door"), "2026-11-21T09:00:00+00:00")
    await hass.async_block_till_done()  # the first update writes
    changed, reported = _record_writes(hass, {lock})

    # Pressing a lock button changes the button's state, not the lock's.
    hass.states.async_set(_cn_entity("lock_door"), "2026-11-21T10:00:00+00:00")
    await hass.async_block_till_done()
    assert changed == [] and reported == []

    hass.states.async_set(_cn_entity("lock_status"), "已解锁")
    await hass.async_block_till_done()
    assert changed == [lock]
    assert hass.states.get(lock).state == "unlocked"


async def test_lock_detail_does_not_restart_the_auto_lock_wait(
    hass: HomeAssistant,
    ford: str,  # noqa: F811
    freezer,
) -> None:
    lock_calls = async_mock_service(hass, "lock", "lock")
    async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)  # unlocked and parked away: a 3-minute wait

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # Still unlocked; only a door's detail changed.
    hass.states.async_set(_entity_id("lock"), "unlocked", {"frontLeft": "UNLOCKED"})
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1, seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(lock_calls) == 1


async def test_door_detail_does_not_restart_the_auto_lock_wait(
    hass: HomeAssistant,
    ford: str,  # noqa: F811
    freezer,
) -> None:
    lock_calls = async_mock_service(hass, "lock", "lock")
    async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("doors"), "Closed", {"hood": "CLOSED"})
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1, seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(lock_calls) == 1


async def test_doors_closing_still_restarts_the_wait(
    hass: HomeAssistant,
    ford: str,  # noqa: F811
    freezer,
) -> None:
    lock_calls = async_mock_service(hass, "lock", "lock")
    async_mock_service(hass, "notify", "mobile_app_my_phone")
    await _setup(hass, ford)

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    hass.states.async_set(_entity_id("doors"), "Open", {"driverFront": "AJAR"})
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("doors"), "Closed", {"driverFront": "CLOSED"})
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1, seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert lock_calls == []  # the wait started again when the door closed
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(lock_calls) == 1


async def test_diagnostics_hide_household_drivers(
    hass: HomeAssistant,
    ford: str,  # noqa: F811
) -> None:
    hass.states.async_set("person.alex", "home", {"friendly_name": "Alex"})
    hass.states.async_set("person.sam", "home", {"friendly_name": "Sam"})
    entry = await _setup(hass, ford)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "phone_tracker": "device_tracker.alex_phone",
            "household_drivers": ["person.alex", "person.sam"],
            "driver_profiles": {"person.sam": {"alerts": ["alarm"]}},
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    entry.runtime_data.set_active_driver("person.sam", manual=True, reason="manual")

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    text = repr(diagnostics)
    for private in ("alex", "Alex", "sam", "Sam"):
        assert private not in text
    options = diagnostics["options"]
    assert options["household_drivers"] == ["person.driver_1", "person.driver_2"]
    assert options["driver_profiles"] == {"person.driver_2": {"alerts": ["alarm"]}}
    assert diagnostics["driving"]["active_driver"] == "person.driver_2"
    assert diagnostics["driving"]["active_driver_name"] == "**REDACTED**"
