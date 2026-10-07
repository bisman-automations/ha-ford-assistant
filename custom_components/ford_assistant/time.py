"""Schedule times for Ford Assistant."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .const import EV_TIMES, TIMES
from .entity import FordAssistantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up time settings."""
    controller = entry.runtime_data
    async_add_entities(
        ScheduleTime(controller, key)
        for key in TIMES
        if controller.is_electric or key not in EV_TIMES
    )


class ScheduleTime(FordAssistantEntity, TimeEntity):
    """When pre-conditioning or the leaving-work prompt runs."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> time:
        """Current time."""
        return self.controller.times[self._key]

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        self.controller.set_time(self._key, value)
