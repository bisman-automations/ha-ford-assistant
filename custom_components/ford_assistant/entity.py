"""Base entity for Ford Assistant."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .compat import PER_ENTRY_DEVICES
from .const import DOMAIN, FORD_DOMAIN
from .controller import FordAssistantController
from .discovery import ford_device


def device_info(controller: FordAssistantController) -> DeviceInfo:
    """Where Ford Assistant's entities live.

    On HA 2026.8 and later, Ford Assistant has its own device that shares the
    Ford vehicle's identifier, so each shows the other under "Linked devices".
    Earlier versions merge devices that share an identifier, so there it only
    passes the identifier and its entities join the Ford vehicle's device.
    """
    vin = controller.vin
    if not PER_ENTRY_DEVICES:
        return DeviceInfo(identifiers={(FORD_DOMAIN, vin)})
    vehicle = ford_device(controller.hass, vin)
    return DeviceInfo(
        identifiers={(DOMAIN, vin), (FORD_DOMAIN, vin)},
        name=controller.name,
        manufacturer=(vehicle.manufacturer if vehicle else None) or "Ford",
        model="Ford Assistant",
        sw_version=controller.version,
        entry_type=DeviceEntryType.SERVICE,
    )


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
        self._attr_device_info = device_info(controller)

    async def async_added_to_hass(self) -> None:
        """Update whenever the controller changes."""
        self.async_on_remove(
            self.controller.async_add_listener(self.async_write_ha_state)
        )
