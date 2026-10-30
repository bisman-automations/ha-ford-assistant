"""Device registry helpers.

Home Assistant 2026.8 made devices belong to a single config entry: identifiers
and connections are unique per config entry, and devices from different
integrations that share one are shown as "Linked devices" instead of being
merged into one device. Ford Assistant needs 2026.8 or newer.
"""

from __future__ import annotations

from collections.abc import Mapping

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


def device_entry_ids(device: dr.DeviceEntry) -> set[str]:
    """Config entries a device belongs to (one, since 2026.8)."""
    entry_id = getattr(device, "config_entry_id", None)
    return {entry_id} if entry_id else set()


def all_devices(hass: HomeAssistant) -> list[dr.DeviceEntry]:
    """Every registered device.

    ``registry.devices`` is a mapping of id to device on 2026.8, and iterates
    over the devices from 2026.9 (using it as a mapping is removed in 2027.9).
    """
    items = dr.async_get(hass).devices
    if isinstance(items, Mapping):
        return list(items.values())
    return list(items)


def devices_with_identifier(
    hass: HomeAssistant, identifier: tuple[str, str]
) -> list[dr.DeviceEntry]:
    """Devices (from any integration) that carry this identifier."""
    return dr.async_get(hass).async_get_devices(identifiers={identifier})


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
