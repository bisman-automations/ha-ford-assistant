"""Ford Assistant: a companion to the Ford integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .const import CONF_VIN, DOMAIN, REQUIRED_ROLES
from .controller import FordAssistantController

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

type FordAssistantConfigEntry = ConfigEntry[FordAssistantController]


async def async_setup_entry(hass: HomeAssistant, entry: FordAssistantConfigEntry) -> bool:
    """Set up Ford Assistant for one vehicle."""
    controller = FordAssistantController(hass, entry)
    await controller.async_load()

    issue_id = f"missing_entities_{entry.entry_id}"
    if missing := [role for role in REQUIRED_ROLES if role not in controller.entities]:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="missing_entities",
            translation_placeholders={
                "vehicle": entry.title,
                "entities": ", ".join(missing),
            },
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="missing_entities",
            translation_placeholders={"vin": entry.data[CONF_VIN]},
        )
    ir.async_delete_issue(hass, DOMAIN, issue_id)

    entry.runtime_data = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    controller.async_start()
    entry.async_on_unload(controller.async_stop)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FordAssistantConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_flush()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: FordAssistantConfigEntry) -> None:
    """Delete saved settings when the entry is removed."""
    from homeassistant.helpers.storage import Store

    from .const import STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
