"""Base entity for Ford Assistant."""

from __future__ import annotations

from homeassistant.core import State, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import FordAssistantController
from .discovery import ford_device


def device_info(controller: FordAssistantController) -> DeviceInfo:
    """Where Ford Assistant's entities live.

    Ford Assistant has its own device that shares the Ford vehicle's
    identifier, so each shows the other under "Linked devices".
    """
    vin = controller.vin
    vehicle = ford_device(controller.hass, vin, controller.source)
    return DeviceInfo(
        identifiers={(DOMAIN, vin), (controller.source, vin)},
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
    _last_written: str | None = None
    _written: State | None = None

    def __init__(self, controller: FordAssistantController, key: str) -> None:
        """Initialise the entity."""
        self.controller = controller
        self._key = key
        self._attr_unique_id = f"{controller.vin}_{key}".lower()
        self._attr_translation_key = key
        self._attr_device_info = device_info(controller)

    async def async_added_to_hass(self) -> None:
        """Update whenever the controller changes."""
        self.async_on_remove(self.controller.async_add_listener(self._async_updated))

    def _shown(self) -> str:
        """What this entity shows, to tell whether a write would change it."""
        return repr(
            (
                self.available,
                self.state,
                self.capability_attributes,
                self.extra_state_attributes,
            )
        )

    @callback
    def _async_updated(self) -> None:
        """Write this entity only if what it shows changed.

        Every setting change and every alert reaches every Ford Assistant
        entity, and almost all of them show the same as before. Any other
        write since (Home Assistant's own, a rename) is written over.
        """
        shown = self._shown()
        current = self.hass.states.get(self.entity_id)
        if (
            current is not None
            and current is self._written
            and shown == self._last_written
        ):
            return
        self.async_write_ha_state()
        self._last_written = shown
        self._written = self.hass.states.get(self.entity_id)

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Keep running when the entity ID is changed (Home Assistant 2026.11+).

        Nothing here is keyed on the entity ID, so the entity carries on as is.
        """
        parent = getattr(super(), "async_entity_id_changed", None)
        if parent is not None:
            parent(old_entity_id)
