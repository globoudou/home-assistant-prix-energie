"""Prix Énergie FR — electricity, gas and water prices for the Energy dashboard."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import PrixEnergieConfigEntry, PrixEnergieCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_FILE = "prix-energie-card.js"
CARD_URL_BASE = f"/{DOMAIN}/{CARD_FILE}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the Lovelace card and load it automatically in the frontend."""
    if hass.http is None or "frontend" not in hass.config.components:
        return True
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.loader import async_get_integration

    integration = await async_get_integration(hass, DOMAIN)
    path = Path(__file__).parent / "frontend" / CARD_FILE
    try:
        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL_BASE, str(path), True)])
    except RuntimeError:  # already registered (integration reloaded)
        _LOGGER.debug("Card path already registered")
    # Version in the query string so browsers fetch the new card after an update.
    add_extra_js_url(hass, f"{CARD_URL_BASE}?v={integration.version}")
    return True


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
