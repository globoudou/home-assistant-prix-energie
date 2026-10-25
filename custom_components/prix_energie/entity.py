"""Base entity and off-peak tracking for Prix Énergie FR."""

from __future__ import annotations

from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ELEC_OPTION,
    CONF_HC_ENTITY,
    CONF_HC_SCHEDULE,
    DEFAULT_HC_SCHEDULE,
    DOMAIN,
    MANUFACTURER,
    OPTION_HPHC,
)
from .coordinator import PrixEnergieCoordinator
from .schedule import ScheduleError, in_schedule, parse_schedule, state_is_off_peak

ENERGY_MODEL = {
    "electricity": "Électricité",
    "gas": "Gaz naturel",
    "water": "Eau",
}


class PrixEnergieEntity(CoordinatorEntity[PrixEnergieCoordinator]):
    """Common entity: one device per energy."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PrixEnergieCoordinator, energy: str, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self.energy = energy
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{energy}")},
            name=f"{entry.title} {ENERGY_MODEL[energy]}",
            manufacturer=MANUFACTURER,
            model=ENERGY_MODEL[energy],
            entry_type=DeviceEntryType.SERVICE,
        )


class OffPeakMixin(PrixEnergieEntity):
    """Adds heures creuses detection and refreshes the state at boundaries."""

    _last_off_peak: bool | None = None

    @property
    def is_hphc(self) -> bool:
        """True when the contract is HP/HC."""
        return self.coordinator.conf.get(CONF_ELEC_OPTION) == OPTION_HPHC

    def off_peak(self) -> bool | None:
        """Return True during heures creuses, None if unknown."""
        conf = self.coordinator.conf
        if entity_id := conf.get(CONF_HC_ENTITY):
            state = self.hass.states.get(entity_id)
            from_entity = state_is_off_peak(state.state if state else None)
            if from_entity is not None:
                return from_entity
        try:
            ranges = parse_schedule(conf.get(CONF_HC_SCHEDULE) or DEFAULT_HC_SCHEDULE)
        except ScheduleError:
            return None
        return in_schedule(ranges, dt_util.now().time())

    async def async_added_to_hass(self) -> None:
        """Track time and the optional off-peak entity."""
        await super().async_added_to_hass()
        if not self.is_hphc:
            return
        self._last_off_peak = self.off_peak()
        self.async_on_remove(async_track_time_change(self.hass, self._async_tick, second=0))
        if entity_id := self.coordinator.conf.get(CONF_HC_ENTITY):
            self.async_on_remove(
                async_track_state_change_event(self.hass, [entity_id], self._async_entity_changed)
            )

    @callback
    def _async_tick(self, _now) -> None:
        current = self.off_peak()
        if current != self._last_off_peak:
            self._last_off_peak = current
            self.async_write_ha_state()

    @callback
    def _async_entity_changed(self, _event: Event[EventStateChangedData]) -> None:
        self._async_tick(None)
