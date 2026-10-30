"""Opening the garage on arrival: only for a real, timely arrival, and logged."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from homeassistant.core import HomeAssistant

from .test_init import AWAY, HOME, _entity_id, _setup, ford  # noqa: F401, F811

GARAGE = "cover.garage"
AT_HOME = {
    "latitude": HOME["latitude"],
    "longitude": HOME["longitude"],
    "gps_accuracy": 10,
}


async def _ready(hass: HomeAssistant, ford_phone: str, freezer: FrozenDateTimeFactory):
    """Ford Assistant with a garage door, past the startup wait, while driving."""
    hass.states.async_set(GARAGE, "closed")
    entry = await _setup(hass, ford_phone)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "garage_cover": GARAGE}
    )
    await hass.async_block_till_done()
    hass.states.async_set(_entity_id("ignition"), "RUN")
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    return entry


def _arrive(hass: HomeAssistant, old_state: str = "not_home", old=AWAY) -> None:
    tracker = _entity_id("tracker")
    hass.states.async_set(tracker, old_state, old)
    hass.states.async_set(tracker, "home", AT_HOME)


async def test_arriving_home_opens_the_garage_and_says_so(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    opens = async_mock_service(hass, "cover", "open_cover")
    logbook = async_capture_events(hass, "logbook_entry")
    await _ready(hass, ford, freezer)

    _arrive(hass)
    await hass.async_block_till_done()

    assert [c.data["entity_id"] for c in opens] == [GARAGE]
    (entry,) = [e for e in logbook if e.data.get("entity_id") == GARAGE]
    assert entry.data["name"].startswith("Ford Assistant")
    assert "arrived home" in entry.data["message"]
    assert entry.data["domain"] == "ford_assistant"
    # The door opening is linked to that Activity line.
    assert opens[0].context.id == entry.context.id


async def test_restart_does_not_open_the_garage(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    opens = async_mock_service(hass, "cover", "open_cover")
    await _ready(hass, ford, freezer)

    # The Ford integration comes back and reports the vehicle at home.
    _arrive(hass, old_state="unavailable", old={})
    await hass.async_block_till_done()
    _arrive(hass, old_state="unknown", old={})
    await hass.async_block_till_done()
    assert opens == []


async def test_no_opening_right_after_a_start(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    opens = async_mock_service(hass, "cover", "open_cover")
    entry = await _ready(hass, ford, freezer)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    _arrive(hass)
    await hass.async_block_till_done()
    assert opens == []


async def test_late_arrival_after_parking_does_not_open(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    """The location caught up after the vehicle was parked: someone's already in."""
    opens = async_mock_service(hass, "cover", "open_cover")
    await _ready(hass, ford, freezer)
    hass.states.async_set(_entity_id("ignition"), "OFF")

    _arrive(hass)
    await hass.async_block_till_done()
    assert opens == []


async def test_door_used_recently_does_not_reopen(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    """Opened and closed by hand a moment ago: a late arrival leaves it closed."""
    opens = async_mock_service(hass, "cover", "open_cover")
    await _ready(hass, ford, freezer)
    hass.states.async_set(GARAGE, "open")
    hass.states.async_set(GARAGE, "closed")
    freezer.tick(timedelta(minutes=2))

    _arrive(hass)
    await hass.async_block_till_done()
    assert opens == []

    # Long after, a real arrival opens it again.
    freezer.tick(timedelta(minutes=15))
    _arrive(hass)
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in opens] == [GARAGE]


async def test_jumpy_location_opens_only_once(
    hass: HomeAssistant, ford: str, freezer: FrozenDateTimeFactory
) -> None:
    opens = async_mock_service(hass, "cover", "open_cover")
    await _ready(hass, ford, freezer)

    _arrive(hass)
    await hass.async_block_till_done()
    assert len(opens) == 1
    # The mock doesn't move the door, so it still reads closed.
    freezer.tick(timedelta(minutes=1))
    _arrive(hass)
    await hass.async_block_till_done()
    assert len(opens) == 1
