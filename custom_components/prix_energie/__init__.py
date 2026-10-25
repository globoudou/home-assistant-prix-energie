"""Prix Énergie FR — electricity, gas and water prices for the Energy dashboard."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PrixEnergieConfigEntry, PrixEnergieCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PrixEnergieConfigEntry) -> bool:
    """Set up an entry."""
    coordinator = PrixEnergieCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: PrixEnergieConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PrixEnergieConfigEntry) -> bool:
    """Unload an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PrixEnergieConfigEntry) -> None:
    """Remove cached prices when the entry is deleted."""
    from homeassistant.helpers.storage import Store

    from .const import DOMAIN, STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
