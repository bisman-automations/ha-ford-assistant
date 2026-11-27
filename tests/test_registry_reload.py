"""1.9.1: only a new entity ID or a removed entity reloads Ford Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_init import _entity_id, _setup, ford  # noqa: F401


async def test_name_icon_area_change_does_not_reload(
    hass: HomeAssistant, ford: str
) -> None:
    entry = await _setup(hass, ford)
    controller = entry.runtime_data
    registry = er.async_get(hass)
    lock_id = _entity_id("lock")

    registry.async_update_entity(lock_id, name="Truck lock", icon="mdi:lock")
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is controller  # not reloaded


async def test_new_entity_id_reloads(hass: HomeAssistant, ford: str) -> None:
    entry = await _setup(hass, ford)
    controller = entry.runtime_data
    registry = er.async_get(hass)
    new_id = "lock.truck"

    registry.async_update_entity(_entity_id("lock"), new_entity_id=new_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not controller
    assert entry.runtime_data.entities["lock"] == new_id
