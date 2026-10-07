"""Last-event sensor for Ford Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .entity import FordAssistantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor."""
    async_add_entities([LastEventSensor(entry.runtime_data, "last_event")])


class LastEventSensor(FordAssistantEntity, SensorEntity):
    """The most recent thing Ford Assistant did or alerted about."""

    @property
    def native_value(self) -> str | None:
        """Event title."""
        event = self.controller.last_event
        return event["title"][:255] if event else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Event details."""
        if (event := self.controller.last_event) is None:
            return None
        return {
            "type": event["type"],
            "message": event["message"],
            "time": event["time"].isoformat(),
        }
