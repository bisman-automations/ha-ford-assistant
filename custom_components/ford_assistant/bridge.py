"""Bridge entities that give FordPass China vehicles marq24-shaped readings.

The rest of Ford Assistant was written against marq24's Ford integration: one
lock entity, one doors sensor whose attributes name the open doors, one tire
sensor reading ``NORMAL_OPERATION``, and so on. FordPass China reports each of
those separately and in Chinese. Rather than teach every alert and the dashboard
about a second shape, Ford Assistant adds these entities for a China vehicle and
combines the readings here.

They only read the FordPass China entities' states and call its services, so
neither integration is imported or patched.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.components.lock import LockEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event

from . import bridge_logic
from .access import async_ensure_allowed
from .const import DOMAIN
from .controller import FordAssistantController
from .entity import FordAssistantEntity
from .sources import SOURCE_CHINA, cn_entity, cn_one_of

DOOR_KEYS = (
    "driver_door",
    "passenger_door",
    "left_rear_door",
    "right_rear_door",
    "tailgate",
    "hood",
    "inner_tailgate",
)
WINDOW_KEYS = (
    "driver_window",
    "passenger_window",
    "left_rear_window",
    "right_rear_window",
    "sunroof",
)
TIRE_KEYS = ("lf_tire", "rf_tire", "lr_tire", "rr_tire")
TIRE_STATUS_KEYS = (
    "lf_tire_status",
    "rf_tire_status",
    "lr_tire_status",
    "rr_tire_status",
)


class BridgeEntity(FordAssistantEntity):
    """A Ford Assistant entity built from one or more FordPass China readings."""

    SOURCE_KEYS: tuple[str, ...] = ()

    def __init__(
        self,
        controller: FordAssistantController,
        key: str,
        icon: str | None = None,
    ) -> None:
        """Initialise with a translation key so the name follows the UI language."""
        super().__init__(controller, key)
        self._attr_translation_key = key
        self._attr_icon = icon

    async def async_added_to_hass(self) -> None:
        """Follow the FordPass China readings this entity is built from."""
        await super().async_added_to_hass()
        entity_ids = [
            entity_id
            for key in self.SOURCE_KEYS
            if (entity_id := cn_entity(self.hass, self.controller.vin, key))
        ]
        if entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, entity_ids, self._source_changed
                )
            )

    @callback
    def _source_changed(self, _event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Usable while at least one of its readings exists and has a state."""
        for key in self.SOURCE_KEYS:
            entity_id = cn_entity(self.hass, self.controller.vin, key)
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is not None and not bridge_logic.is_bad(state.state):
                return True
        return False

    def _state(self, key: str) -> str | None:
        """The raw state of one FordPass China reading."""
        entity_id = cn_entity(self.hass, self.controller.vin, key)
        state = self.hass.states.get(entity_id) if entity_id else None
        return None if state is None else state.state

    def _states(self, keys) -> dict[str, str | None]:
        return {key: self._state(key) for key in keys}

    async def _async_ensure_allowed(self, action: str) -> None:
        """Refuse the action when access or the driving mode doesn't allow it."""
        await async_ensure_allowed(self.hass, self._context)
        if not self.controller.allows_action(action):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_blocked",
                translation_placeholders={
                    "action": action,
                    "mode": self.controller.driving_mode,
                },
            )

    async def _call_source(self, key: str, domain: str, service: str) -> None:
        """Call a service on the FordPass China entity for that key."""
        entity_id = cn_entity(self.hass, self.controller.vin, key)
        if entity_id is None:
            raise HomeAssistantError(f"FordPass China entity for {key} is missing")
        await self.hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )


@dataclass(frozen=True)
class BridgeSensorSpec:
    """One bridge sensor and which FordPass China readings it needs."""

    key: str
    icon: str
    requires: tuple[str, ...]
    unit: str | None = None


SENSOR_SPECS: tuple[BridgeSensorSpec, ...] = (
    BridgeSensorSpec("bridge_ignition", "mdi:engine", ("ignition",)),
    BridgeSensorSpec("bridge_doors", "mdi:car-door", DOOR_KEYS),
    BridgeSensorSpec("bridge_windows", "mdi:window-closed", WINDOW_KEYS),
    BridgeSensorSpec(
        "bridge_tires",
        "mdi:car-tire-alert",
        (*TIRE_KEYS, *TIRE_STATUS_KEYS),
    ),
    BridgeSensorSpec("bridge_alarm", "mdi:alarm", ("alarm_status",)),
    BridgeSensorSpec("bridge_fuel", "mdi:fuel", ("fuel_level",), unit="%"),
    BridgeSensorSpec(
        "bridge_soc", "mdi:battery-high", ("battery_fill_level",), unit="%"
    ),
    BridgeSensorSpec("bridge_ev_plug", "mdi:power-plug", ("plug_status",)),
    BridgeSensorSpec("bridge_ev_charging", "mdi:power-plug", ("charging_status",)),
)


class BridgeSensor(BridgeEntity, SensorEntity):
    """A sensor combining FordPass China readings into one marq24-shaped value."""

    def __init__(
        self, controller: FordAssistantController, spec: BridgeSensorSpec
    ) -> None:
        """Initialise from the spec."""
        super().__init__(controller, spec.key, spec.icon)
        self._spec = spec
        self.SOURCE_KEYS = spec.requires
        if spec.unit:
            self._attr_native_unit_of_measurement = spec.unit

    @property
    def native_value(self):
        """The value Ford Assistant's alerts and dashboard expect."""
        key = self._spec.key
        if key == "bridge_ignition":
            return bridge_logic.ignition_state(self._state("ignition"))
        if key == "bridge_doors":
            return bridge_logic.doors(self._states(DOOR_KEYS))[0]
        if key == "bridge_windows":
            return bridge_logic.windows(self._states(WINDOW_KEYS))
        if key == "bridge_tires":
            return bridge_logic.tires(
                self._states(TIRE_KEYS), self._states(TIRE_STATUS_KEYS)
            )[0]
        if key == "bridge_alarm":
            return bridge_logic.alarm_state(self._state("alarm_status"))
        if key == "bridge_fuel":
            return self._numeric("fuel_level")
        if key == "bridge_soc":
            return self._numeric("battery_fill_level")
        if key == "bridge_ev_plug":
            return bridge_logic.plug_state(self._state("plug_status"))
        if key == "bridge_ev_charging":
            return bridge_logic.charging_state(self._state("charging_status"))
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Per-door, per-window and per-wheel detail where it applies."""
        key = self._spec.key
        if key == "bridge_doors":
            return bridge_logic.doors(self._states(DOOR_KEYS))[1]
        if key == "bridge_tires":
            return bridge_logic.tires(
                self._states(TIRE_KEYS), self._states(TIRE_STATUS_KEYS)
            )[1]
        if key == "bridge_fuel":
            return self._range("distance_to_empty", "fuelRange")
        if key == "bridge_soc":
            return self._range("ev_dte", "batteryRange")
        return {}

    def _numeric(self, key: str):
        """A reading as a number, without a pointless ``.0``."""
        value = bridge_logic.number(self._state(key))
        if value is not None and value.is_integer():
            return int(value)
        return value

    def _range(self, source_key: str, attribute: str) -> dict:
        value = self._numeric(source_key)
        return {attribute: value} if value is not None else {}


def bridge_sensors(controller: FordAssistantController) -> list[BridgeSensor]:
    """The bridge sensors a vehicle needs, skipping readings it doesn't have."""
    if controller.source != SOURCE_CHINA:
        return []
    entities: list[BridgeSensor] = []
    for spec in SENSOR_SPECS:
        if not any(
            cn_entity(controller.hass, controller.vin, key) for key in spec.requires
        ):
            continue
        entities.append(BridgeSensor(controller, spec))
    return entities


class VehicleLock(BridgeEntity, LockEntity):
    """The vehicle's lock, backed by FordPass China's lock and unlock actions."""

    SOURCE_KEYS = ("lock_status", "lock_door", "unlock_door")

    def __init__(self, controller: FordAssistantController) -> None:
        super().__init__(controller, "bridge_lock", "mdi:lock")

    @property
    def is_locked(self) -> bool | None:
        """Locked, unlocked, or unknown while the car hasn't reported yet."""
        state = bridge_logic.lock_state(self._state("lock_status"))
        if state is None:
            return None
        return state == "locked"

    async def async_lock(self, **kwargs) -> None:
        """Lock the car through the FordPass China action button."""
        await self._async_ensure_allowed("lock")
        await self._call_source("lock_door", "button", "press")

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the car through the FordPass China action button."""
        await self._async_ensure_allowed("unlock")
        await self._call_source("unlock_door", "button", "press")


class RemoteStart(BridgeEntity, SwitchEntity):
    """Remote start, backed by FordPass China's engine switch."""

    SOURCE_KEYS = ("engine", "remote_start")

    def __init__(self, controller: FordAssistantController) -> None:
        super().__init__(controller, "bridge_remote_start", "mdi:engine")

    @property
    def is_on(self) -> bool | None:
        """Whether the engine is running from a remote start."""
        if (
            state := bridge_logic.remote_start_state(self._state("engine"))
        ) is not None:
            return state == "on"
        if (
            state := bridge_logic.remote_start_state(self._state("remote_start"))
        ) is not None:
            return state == "on"
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Start the engine."""
        await self._async_ensure_allowed("remote_start")
        await self._call_source("engine", "switch", "turn_on")

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the engine."""
        await self._async_ensure_allowed("remote_start")
        await self._call_source("engine", "switch", "turn_off")


class HonkButton(BridgeEntity, ButtonEntity):
    """Honk and flash, backed by FordPass China's honk or horn-and-light switch."""

    SOURCE_KEYS = ("honk", "va_switch")

    def __init__(self, controller: FordAssistantController) -> None:
        super().__init__(controller, "bridge_honk", "mdi:car-light-high")

    async def async_press(self) -> None:
        """Trigger the momentary honk switch (horn plus lights when available)."""
        await self._async_ensure_allowed("honk")
        entity_id = cn_one_of(self.hass, self.controller.vin, "honk")
        if entity_id is None:
            raise HomeAssistantError("FordPass China honk entity is missing")
        await self.hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
