"""Heures creuses binary sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ELEC_OPTION, ENERGY_ELEC, OPTION_HPHC
from .coordinator import PrixEnergieConfigEntry, PrixEnergieCoordinator
from .entity import OffPeakMixin


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrixEnergieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the off-peak sensor for HP/HC contracts."""
    coordinator = entry.runtime_data
    if ENERGY_ELEC in coordinator.energies and coordinator.conf.get(CONF_ELEC_OPTION) == OPTION_HPHC:
        async_add_entities([OffPeakBinarySensor(coordinator)])


class OffPeakBinarySensor(OffPeakMixin, BinarySensorEntity):
    """On during heures creuses."""

    _attr_icon = "mdi:clock-time-ten-outline"

    def __init__(self, coordinator: PrixEnergieCoordinator) -> None:
        super().__init__(coordinator, ENERGY_ELEC, "off_peak")

    @property
    def is_on(self) -> bool | None:
        """Return True during heures creuses."""
        return self.off_peak()

    @property
    def available(self) -> bool:
        """Always computable from the schedule."""
        return True
