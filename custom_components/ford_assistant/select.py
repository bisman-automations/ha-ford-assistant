"""Who's driving, and which household person is the active driver."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FordAssistantConfigEntry
from .access import async_ensure_allowed
from .driving import ACTIVE_DRIVER_NONE, DRIVING_MODES
from .entity import FordAssistantEntity

# Coordinator or push updates; nothing polls on its own.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FordAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the driving-mode selects."""
    controller = entry.runtime_data
    async_add_entities([DrivingModeSelect(controller), ActiveDriverSelect(controller)])


class DrivingModeSelect(FordAssistantEntity, SelectEntity):
    """Household, Service, or Guest.

    The state is restored from the controller's store, which is written
    through restarts and reloads. Attributes carry the same picture the
    driving-status sensor exposes, so an automation can listen to either.
    """

    _attr_options = list(DRIVING_MODES)
    _attr_translation_key = "driving_mode"

    def __init__(self, controller) -> None:
        """Initialise the select."""
        super().__init__(controller, "driving_mode")

    @property
    def current_option(self) -> str:
        """The mode in effect."""
        return self.controller.driving_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Mode, driver, and the effective allow and keep lists."""
        return self.controller.driving_attributes()

    async def async_select_option(self, option: str) -> None:
        """Change mode. Service and Guest use their configured auto-revert."""
        await async_ensure_allowed(self.hass, self._context)
        self.controller.set_driving_mode(option)


class ActiveDriverSelect(FordAssistantEntity, SelectEntity):
    """The household person currently driving, or nobody.

    Options are the eligible household drivers plus ``none``. Choosing one
    is a manual override: automatic detection won't replace it until the
    vehicle is parked at home. The choice is remembered in other modes and
    takes effect again when the mode returns to Household.
    """

    _attr_translation_key = "active_driver"

    def __init__(self, controller) -> None:
        """Initialise the select."""
        super().__init__(controller, "active_driver")

    def _labels(self) -> dict[str, str]:
        """Each eligible person's name (what the list shows) and their person
        entity. Two people with the same name get "(2)" after the second."""
        labels: dict[str, str] = {}
        for entity_id in self.controller.household_drivers:
            state = self.hass.states.get(entity_id) if self.hass else None
            name = (state.name if state else None) or entity_id
            label, count = name, 2
            while label in labels or label == ACTIVE_DRIVER_NONE:
                label, count = f"{name} ({count})", count + 1
            labels[label] = entity_id
        return labels

    @property
    def options(self) -> list[str]:
        """Nobody, then each eligible household person, by name."""
        return [ACTIVE_DRIVER_NONE, *self._labels()]

    @property
    def current_option(self) -> str:
        """The active driver's name, or nobody."""
        driver = self.controller.active_driver
        if driver is None:
            return ACTIVE_DRIVER_NONE
        for label, entity_id in self._labels().items():
            if entity_id == driver:
                return label
        return ACTIVE_DRIVER_NONE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Whether the choice was made by hand, the driver's name and person."""
        return {
            "manual_driver": self.controller.active_driver_manual,
            "active_driver_name": self.controller.active_driver_name,
            # The person entity, for automations (the state is their name).
            "person": self.controller.active_driver,
            "in_effect": self.controller.driving_mode == "household",
        }

    async def async_select_option(self, option: str) -> None:
        """Set the driver by hand (a name from the list)."""
        await async_ensure_allowed(self.hass, self._context)
        driver = None if option == ACTIVE_DRIVER_NONE else self._labels().get(option)
        self.controller.set_active_driver(driver, manual=True, reason="manual")
