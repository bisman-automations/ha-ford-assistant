"""Feature switches for Ford Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .const import EV_FEATURES, FEATURES
from .entity import FordAssistantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up feature switches."""
    controller = entry.runtime_data
    async_add_entities(
        FeatureSwitch(controller, key)
        for key in FEATURES
        if controller.is_electric or key not in EV_FEATURES
    )


class FeatureSwitch(FordAssistantEntity, SwitchEntity):
    """Turns one Ford Assistant feature on or off."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        """Whether the feature is enabled."""
        return self.controller.features[self._key]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the feature."""
        self.controller.set_feature(self._key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the feature."""
        self.controller.set_feature(self._key, False)
