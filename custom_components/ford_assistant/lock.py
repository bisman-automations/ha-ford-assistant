"""Lock platform: the bridge lock FordPass China no longer ships."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .bridge import VehicleLock
from .sources import SOURCE_CHINA, cn_entity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the bridge lock when the FordPass China vehicle supports it."""
    controller = entry.runtime_data
    if controller.source != SOURCE_CHINA:
        return
    if not all(
        cn_entity(hass, controller.vin, key)
        for key in ("lock_status", "lock_door", "unlock_door")
    ):
        return
    async_add_entities([VehicleLock(controller)])
