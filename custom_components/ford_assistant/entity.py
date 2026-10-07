"""Base entity for Ford Assistant."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import FORD_DOMAIN
from .controller import FordAssistantController


class FordAssistantEntity(Entity):
    """Lives on the Ford integration's vehicle device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: FordAssistantController, key: str) -> None:
        """Initialise the entity."""
        self.controller = controller
        self._key = key
        self._attr_unique_id = f"{controller.vin}_{key}".lower()
        self._attr_translation_key = key
        # Identifiers only: links to the existing Ford vehicle device instead
        # of creating a new one, so these entities appear on the same page.
        self._attr_device_info = DeviceInfo(identifiers={(FORD_DOMAIN, controller.vin)})

    async def async_added_to_hass(self) -> None:
        """Update whenever the controller changes."""
        self.async_on_remove(
            self.controller.async_add_listener(self.async_write_ha_state)
        )
