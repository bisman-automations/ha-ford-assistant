"""Feature switches for Ford Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .access import async_ensure_allowed
from .bridge import RemoteStart
from .const import EV_FEATURES, FEATURES
from .entity import FordAssistantEntity
from .sources import SOURCE_CHINA, cn_entity

# Coordinator or push updates; nothing polls on its own.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up feature switches."""
    controller = entry.runtime_data
    entities = [
        FeatureSwitch(controller, key)
        for key in FEATURES
        if controller.is_electric or key not in EV_FEATURES
    ]
    if controller.source == SOURCE_CHINA and cn_entity(hass, controller.vin, "engine"):
        entities.append(RemoteStart(controller))
    async_add_entities(entities)


class FeatureSwitch(FordAssistantEntity, SwitchEntity):
    """Turns one Ford Assistant feature on or off."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        """Whether the feature is enabled."""
        return self.controller.features[self._key]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the feature."""
        await async_ensure_allowed(self.hass, self._context)
        self.controller.set_feature(self._key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the feature."""
        await async_ensure_allowed(self.hass, self._context)
        self.controller.set_feature(self._key, False)
