"""Which Ford integration a vehicle comes from, and where its entities are.

Ford Assistant works with two integrations:

* marq24's Ford integration (``fordpass``): entity unique ids are
  ``fordpass_uid_{vin}_{key}`` and everything it needs is one entity per role.
* FordPass China (``fordpass_cn``): unique ids are ``{sha256(vin)}-{key}`` and
  the vehicle's readings are split over one entity per door, window and wheel.
  Ford Assistant adds its own bridge entities (``{token}_bridge_...``) that
  combine those readings into the shapes the rest of the integration expects.

Nothing here imports from either integration: only the entity registry is read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_SOURCE, FORD_DOMAIN

SOURCE_FORDPASS = FORD_DOMAIN
SOURCE_CHINA = "fordpass_cn"
SOURCES = (SOURCE_FORDPASS, SOURCE_CHINA)
SOURCE_LABELS: Mapping[str, str] = {
    SOURCE_FORDPASS: "Ford",
    SOURCE_CHINA: "FordPass China",
}

# FordPass China entity key -> its platform, for the readings Ford Assistant
# uses directly or through a bridge.
CN_KEYS: Mapping[str, str] = {
    "lock_status": "sensor",
    "ignition": "sensor",
    "driver_door": "sensor",
    "passenger_door": "sensor",
    "left_rear_door": "sensor",
    "right_rear_door": "sensor",
    "tailgate": "sensor",
    "hood": "sensor",
    "inner_tailgate": "sensor",
    "driver_window": "sensor",
    "passenger_window": "sensor",
    "left_rear_window": "sensor",
    "right_rear_window": "sensor",
    "sunroof": "sensor",
    "lf_tire": "sensor",
    "rf_tire": "sensor",
    "lr_tire": "sensor",
    "rr_tire": "sensor",
    "lf_tire_status": "sensor",
    "rf_tire_status": "sensor",
    "lr_tire_status": "sensor",
    "rr_tire_status": "sensor",
    "alarm_status": "sensor",
    "plug_status": "sensor",
    "charging_status": "sensor",
    "fuel_level": "sensor",
    "distance_to_empty": "sensor",
    "battery_fill_level": "sensor",
    "ev_dte": "sensor",
    "odometer": "sensor",
    "prognostic": "sensor",
    "auto_off_remaining": "sensor",
    "remote_start": "sensor",
    "manual_refresh": "button",
    "lock_door": "button",
    "unlock_door": "button",
    "engine": "switch",
    "honk": "switch",
    "va_switch": "switch",
    "tracker": "device_tracker",
    "vehicle_image": "image",
    "vehicle_overlook_image": "image",
}

# Some cars only get one of these; either will do.
CN_ALIASES: Mapping[str, tuple[str, ...]] = {
    "image": ("vehicle_image", "vehicle_overlook_image"),
    "honk": ("va_switch", "honk"),
}

# Roles read straight from FordPass China, no bridge needed.
CN_DIRECT_ROLES: Mapping[str, tuple[str, str]] = {
    "tracker": ("device_tracker", "tracker"),
    "refresh": ("button", "manual_refresh"),
    "image": ("image", "vehicle_image"),
    "odometer": ("sensor", "odometer"),
    "oil": ("sensor", "prognostic"),
    "countdown": ("sensor", "auto_off_remaining"),
}

# Roles a bridge entity supplies. The bridge entity lives in Ford Assistant's
# own domain and carries the unique id suffix below.
CN_BRIDGE_ROLES: Mapping[str, tuple[str, str]] = {
    "lock": ("lock", "bridge_lock"),
    "ignition": ("sensor", "bridge_ignition"),
    "doors": ("sensor", "bridge_doors"),
    "windows": ("sensor", "bridge_windows"),
    "tires": ("sensor", "bridge_tires"),
    "alarm": ("sensor", "bridge_alarm"),
    "fuel": ("sensor", "bridge_fuel"),
    "soc": ("sensor", "bridge_soc"),
    "ev_plug": ("sensor", "bridge_ev_plug"),
    "ev_charging": ("sensor", "bridge_ev_charging"),
    "remote_start": ("switch", "bridge_remote_start"),
    "honk": ("button", "bridge_honk"),
}

# Readings that only electric and plug-in vehicles report.
CN_EV_KEYS = ("battery_fill_level", "plug_status", "charging_status", "ev_dte")


@dataclass(frozen=True)
class Vehicle:
    """A vehicle one of the Ford integrations set up."""

    token: str  # VIN for marq24, the sha256 prefix for FordPass China
    source: str
    name: str

    @property
    def unique_id(self) -> str:
        """Config entry unique id, namespaced by source."""
        return (
            self.token
            if self.source == SOURCE_FORDPASS
            else f"{self.source}:{self.token}"
        )


def source_of(entry: ConfigEntry) -> str:
    """Which integration a config entry's vehicle came from."""
    source = entry.data.get(CONF_SOURCE)
    return source if source in SOURCES else SOURCE_FORDPASS


def cn_entity(hass: HomeAssistant, token: str, key: str) -> str | None:
    """The entity id of one FordPass China reading, or None."""
    platform = CN_KEYS.get(key)
    if platform is None:
        return None
    unique_id = f"{token}-{key}".lower()
    return er.async_get(hass).async_get_entity_id(platform, SOURCE_CHINA, unique_id)


def cn_has(hass: HomeAssistant, token: str, key: str) -> bool:
    """Whether the FordPass China integration created that reading."""
    return cn_one_of(hass, token, key) is not None


def cn_one_of(hass: HomeAssistant, token: str, key: str) -> str | None:
    """The first existing entity for a reading that has more than one key."""
    for candidate in CN_ALIASES.get(key, (key,)):
        if entity_id := cn_entity(hass, token, candidate):
            return entity_id
    return None
