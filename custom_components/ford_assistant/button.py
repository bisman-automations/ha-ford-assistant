"""Button platform: the bridge honk action for FordPass China vehicles."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .bridge import HonkButton
from .sources import SOURCE_CHINA, cn_has

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the bridge honk button when the vehicle supports it."""
    controller = entry.runtime_data
    if controller.source != SOURCE_CHINA:
        return
    if not cn_has(hass, controller.vin, "honk"):
        return
    async_add_entities([HonkButton(controller)])
