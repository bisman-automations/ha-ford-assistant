"""Find the Ford integration's vehicles and their entities."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import FORD_DOMAIN, FORD_ENTITY_KEYS


def ford_vehicles(hass: HomeAssistant) -> dict[str, str]:
    """Return {vin: display name} for every vehicle the Ford integration set up."""
    vehicles: dict[str, str] = {}
    for device in dr.async_get(hass).devices.values():
        for domain, identifier in device.identifiers:
            if domain == FORD_DOMAIN:
                vehicles[identifier] = vehicle_name(device, identifier)
    return vehicles


def vehicle_name(device: dr.DeviceEntry | None, vin: str) -> str:
    """A friendly name for the vehicle."""
    if device is not None:
        if device.name_by_user:
            return device.name_by_user
        if device.model and device.model.strip() not in ("", "unknown"):
            return f"{device.model.strip()} ({vin[-6:]})"
    return f"Ford {vin[-6:]}"


def ford_device(hass: HomeAssistant, vin: str) -> dr.DeviceEntry | None:
    """The Ford integration's device for this VIN."""
    return dr.async_get(hass).async_get_device(identifiers={(FORD_DOMAIN, vin)})


def resolve_entities(hass: HomeAssistant, vin: str) -> dict[str, str]:
    """Map each role in FORD_ENTITY_KEYS to the entity_id it currently has.

    Matching on unique_id rather than entity_id means renamed entities still
    resolve. Roles the vehicle doesn't support are simply absent.
    """
    registry = er.async_get(hass)
    resolved: dict[str, str] = {}
    for role, (platform, key) in FORD_ENTITY_KEYS.items():
        unique_id = f"fordpass_uid_{vin}_{key}".lower()
        if entity_id := registry.async_get_entity_id(platform, FORD_DOMAIN, unique_id):
            resolved[role] = entity_id
    return resolved
