"""Find the Ford integration's vehicles and their entities."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .compat import all_devices, device_in_domain, devices_with_identifier
from .const import DOMAIN, FORD_DOMAIN, FORD_ENTITY_KEYS
from .sources import (
    CN_BRIDGE_ROLES,
    CN_DIRECT_ROLES,
    SOURCE_CHINA,
    SOURCE_FORDPASS,
    Vehicle,
    cn_one_of,
    source_of,
)


def ford_vehicles(hass: HomeAssistant) -> dict[str, Vehicle]:
    """Return {vehicle token: Vehicle} for every vehicle either Ford integration set up."""
    vehicles: dict[str, Vehicle] = {}
    for device in all_devices(hass):
        # Only each Ford integration's own device, not linked devices (like
        # Ford Assistant's) that reuse its identifier.
        for source in (SOURCE_FORDPASS, SOURCE_CHINA):
            if device_in_domain(hass, [device], source) is None:
                continue
            for domain, identifier in device.identifiers:
                if domain != source:
                    continue
                vehicles[identifier] = Vehicle(
                    token=identifier,
                    source=source,
                    name=vehicle_name(device, identifier),
                )
    return vehicles


def vehicle_name(device: dr.DeviceEntry | None, vin: str) -> str:
    """A friendly name for the vehicle."""
    if device is not None:
        if device.name_by_user:
            return device.name_by_user
        if device.model and device.model.strip() not in ("", "unknown"):
            return f"{device.model.strip()} ({vin[-6:]})"
    return f"Ford {vin[-6:]}"


def ford_device(
    hass: HomeAssistant, vin: str, source: str = SOURCE_FORDPASS
) -> dr.DeviceEntry | None:
    """The Ford integration's device for this vehicle."""
    devices = devices_with_identifier(hass, (source, vin))
    return device_in_domain(hass, devices, source) or (devices[0] if devices else None)


def resolve_entities(
    hass: HomeAssistant, vin: str, source: str = SOURCE_FORDPASS
) -> dict[str, str]:
    """Map each role Ford Assistant needs to the entity_id it currently has.

    Matching on unique_id rather than entity_id means renamed entities still
    resolve. Roles the vehicle doesn't support are simply absent.

    For FordPass China, roles come from two places: readings that map straight
    across, and Ford Assistant's own bridge entities that combine the split
    per-door, per-window and per-wheel readings.
    """
    registry = er.async_get(hass)
    resolved: dict[str, str] = {}
    if source == SOURCE_CHINA:
        for role, (_platform, key) in CN_DIRECT_ROLES.items():
            # Some cars have one of two possible entities for a reading.
            if entity_id := cn_one_of(hass, vin, key):
                resolved[role] = entity_id
        for role, (platform, key) in CN_BRIDGE_ROLES.items():
            if entity_id := registry.async_get_entity_id(
                platform, DOMAIN, f"{vin}_{key}".lower()
            ):
                resolved[role] = entity_id
        return resolved

    for role, (platform, key) in FORD_ENTITY_KEYS.items():
        unique_id = f"fordpass_uid_{vin}_{key}".lower()
        if entity_id := registry.async_get_entity_id(platform, FORD_DOMAIN, unique_id):
            resolved[role] = entity_id
    return resolved


__all__ = [
    "ford_device",
    "ford_vehicles",
    "resolve_entities",
    "source_of",
    "vehicle_name",
]
