"""Threshold and delay settings for Ford Assistant."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .const import NUMBERS
from .entity import FordAssistantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number settings."""
    controller = entry.runtime_data
    async_add_entities(SettingNumber(controller, key) for key in NUMBERS)


class SettingNumber(FordAssistantEntity, NumberEntity):
    """An adjustable threshold or delay."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, controller, key: str) -> None:
        """Initialise from the spec."""
        super().__init__(controller, key)
        spec = NUMBERS[key]
        self._attr_native_min_value = spec.min
        self._attr_native_max_value = spec.max
        self._attr_native_step = spec.step
        self._attr_native_unit_of_measurement = spec.unit

    @property
    def native_value(self) -> float:
        """Current setting."""
        return self.controller.numbers[self._key]

    async def async_set_native_value(self, value: float) -> None:
        """Change the setting."""
        self.controller.set_number(self._key, value)
