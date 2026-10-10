"""Device registry helpers that work before and after HA 2026.8.

Home Assistant 2026.8 made devices belong to a single config entry: identifiers
and connections are unique per config entry, and devices from different
integrations that share one are shown as "Linked devices" instead of being
merged into one device.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

# One device per config entry, linked by shared identifiers/connections.
PER_ENTRY_DEVICES: bool = hasattr(dr.DeviceRegistry, "async_get_device_by_identifier")


def device_entry_ids(device: dr.DeviceEntry) -> set[str]:
    """Config entries a device belongs to."""
    if PER_ENTRY_DEVICES and (entry_id := getattr(device, "config_entry_id", None)):
        return {entry_id}
    return set(device.config_entries)


def all_devices(hass: HomeAssistant) -> list[dr.DeviceEntry]:
    """Every registered device."""
    registry = dr.async_get(hass)
    if PER_ENTRY_DEVICES:
        return list(registry.devices)
    return list(registry.devices.values())


def devices_with_identifier(
    hass: HomeAssistant, identifier: tuple[str, str]
) -> list[dr.DeviceEntry]:
    """Devices (from any integration) that carry this identifier."""
    registry = dr.async_get(hass)
    if PER_ENTRY_DEVICES:
        return registry.async_get_devices(identifiers={identifier})
    device = registry.async_get_device(identifiers={identifier})
    return [device] if device else []


def device_in_domain(
    hass: HomeAssistant, devices: list[dr.DeviceEntry], domain: str
) -> dr.DeviceEntry | None:
    """The first device owned by an integration with this domain."""
    for device in devices:
        for entry_id in device_entry_ids(device):
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is not None and entry.domain == domain:
                return device
    return None
