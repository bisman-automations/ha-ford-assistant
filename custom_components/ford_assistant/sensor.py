"""Last-event sensor for Ford Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .bridge import bridge_sensors
from .driving import DRIVING_MODES
from .entity import FordAssistantEntity

# Coordinator or push updates; nothing polls on its own.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    controller = entry.runtime_data
    async_add_entities(
        [
            LastEventSensor(controller, "last_event"),
            DrivingStatusSensor(controller),
            *bridge_sensors(controller),
        ]
    )


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


class DrivingStatusSensor(FordAssistantEntity, SensorEntity):
    """Current driving mode, with the driver and the effective lists.

    The state is the mode (``household``, ``service`` or ``guest``). The
    attributes are there for automations that want the active driver and the
    actions Ford Assistant will and won't run. The Who's driving select
    carries the same attributes.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(DRIVING_MODES)
    _attr_translation_key = "driving_status"

    def __init__(self, controller) -> None:
        """Initialise the sensor."""
        super().__init__(controller, "driving_status")

    @property
    def native_value(self) -> str:
        """The mode in effect."""
        return self.controller.driving_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Driver and the effective allow, block and keep lists."""
        return self.controller.driving_attributes()
