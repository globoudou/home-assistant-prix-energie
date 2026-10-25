"""Price sensors usable in the Home Assistant Energy dashboard."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ENERGY_ELEC, ENERGY_GAS, ENERGY_WATER, OPTION_BASE, OPTION_HPHC
from .coordinator import PriceData, PrixEnergieConfigEntry, PrixEnergieCoordinator
from .entity import OffPeakMixin, PrixEnergieEntity

PRICE_KWH = f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
PRICE_M3 = f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}"


@dataclass(frozen=True, kw_only=True)
class PriceSensorDescription(SensorEntityDescription):
    """Describes a price sensor."""

    energy: str
    value_fn: Callable[[PriceData], float | None]
    elec_options: tuple[str, ...] | None = None  # electricity options it applies to


def _price(**kw) -> dict[str, Any]:
    return {
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 4,
        **kw,
    }


def _subscription(**kw) -> dict[str, Any]:
    return {
        "device_class": SensorDeviceClass.MONETARY,
        "native_unit_of_measurement": CURRENCY_EURO,
        "suggested_display_precision": 2,
        **kw,
    }


DESCRIPTIONS: tuple[PriceSensorDescription, ...] = (
    PriceSensorDescription(
        key="electricity_price_base",
        energy=ENERGY_ELEC,
        elec_options=(OPTION_BASE,),
        native_unit_of_measurement=PRICE_KWH,
        icon="mdi:cash",
        value_fn=lambda d: d.electricity.base,
        **_price(),
    ),
    PriceSensorDescription(
        key="electricity_price_hp",
        energy=ENERGY_ELEC,
        elec_options=(OPTION_HPHC,),
        native_unit_of_measurement=PRICE_KWH,
        icon="mdi:weather-sunny",
        value_fn=lambda d: d.electricity.hp,
        **_price(),
    ),
    PriceSensorDescription(
        key="electricity_price_hc",
        energy=ENERGY_ELEC,
        elec_options=(OPTION_HPHC,),
        native_unit_of_measurement=PRICE_KWH,
        icon="mdi:weather-night",
        value_fn=lambda d: d.electricity.hc,
        **_price(),
    ),
    PriceSensorDescription(
        key="electricity_subscription",
        energy=ENERGY_ELEC,
        icon="mdi:file-document-outline",
        value_fn=lambda d: d.electricity.subscription,
        **_subscription(),
    ),
    PriceSensorDescription(
        key="gas_price_kwh",
        energy=ENERGY_GAS,
        native_unit_of_measurement=PRICE_KWH,
        icon="mdi:fire",
        value_fn=lambda d: d.gas.kwh,
        **_price(),
    ),
    PriceSensorDescription(
        key="gas_price_m3",
        energy=ENERGY_GAS,
        native_unit_of_measurement=PRICE_M3,
        icon="mdi:fire",
        value_fn=lambda d: d.gas.m3,
        **_price(),
    ),
    PriceSensorDescription(
        key="gas_subscription",
        energy=ENERGY_GAS,
        icon="mdi:file-document-outline",
        value_fn=lambda d: d.gas.subscription,
        **_subscription(),
    ),
    PriceSensorDescription(
        key="water_price",
        energy=ENERGY_WATER,
        native_unit_of_measurement=PRICE_M3,
        icon="mdi:water",
        value_fn=lambda d: d.water.m3,
        **_price(),
    ),
    PriceSensorDescription(
        key="water_subscription",
        energy=ENERGY_WATER,
        icon="mdi:file-document-outline",
        value_fn=lambda d: d.water.subscription,
        **_subscription(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrixEnergieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors for the configured energies."""
    coordinator = entry.runtime_data
    energies = coordinator.energies
    option = coordinator.data.electricity.option if coordinator.data.electricity else None

    entities: list[SensorEntity] = []
    if ENERGY_ELEC in energies:
        entities.append(CurrentElectricityPriceSensor(coordinator))
    for desc in DESCRIPTIONS:
        if desc.energy not in energies:
            continue
        if desc.elec_options and option not in desc.elec_options:
            continue
        entities.append(PriceSensor(coordinator, desc))
    async_add_entities(entities)


class PriceSensor(PrixEnergieEntity, SensorEntity):
    """A price or subscription value."""

    entity_description: PriceSensorDescription

    def __init__(self, coordinator: PrixEnergieCoordinator, desc: PriceSensorDescription) -> None:
        super().__init__(coordinator, desc.energy, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> float | None:
        """Return the value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Unavailable only when no value is known at all."""
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Source details."""
        data = self.coordinator.data
        attrs: dict[str, Any] = {}
        if self.energy == ENERGY_ELEC and data.electricity:
            elec = data.electricity
            attrs = {"source": elec.source, "option": elec.option}
            if elec.valid_from:
                attrs["valid_from"] = elec.valid_from
            if elec.stale:
                attrs["stale"] = True
        elif self.energy == ENERGY_GAS and data.gas:
            attrs = {
                "source": data.gas.source,
                "profile": data.gas.profile,
                "kwh_per_m3": data.gas.kwh_per_m3,
            }
            if data.gas.period:
                attrs["period"] = data.gas.period
        if self.entity_description.device_class == SensorDeviceClass.MONETARY:
            value = self.native_value
            if value is not None:
                attrs["per_month"] = round(value / 12, 2)
                attrs["per_day"] = round(value / 365, 4)
        if data.errors:
            attrs["last_errors"] = data.errors
        return attrs


class CurrentElectricityPriceSensor(OffPeakMixin, SensorEntity):
    """Price of the kWh right now (HP or HC) — use this in the Energy dashboard."""

    _attr_native_unit_of_measurement = PRICE_KWH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4
    _attr_icon = "mdi:currency-eur"

    def __init__(self, coordinator: PrixEnergieCoordinator) -> None:
        super().__init__(coordinator, ENERGY_ELEC, "electricity_price")

    @property
    def native_value(self) -> float | None:
        """Return the price in force."""
        elec = self.coordinator.data.electricity
        if elec is None:
            return None
        if elec.option == OPTION_BASE:
            return elec.base
        off_peak = self.off_peak()
        if off_peak is None:
            return None
        return elec.hc if off_peak else elec.hp

    @property
    def available(self) -> bool:
        """Available when a price is known."""
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Current tariff period."""
        elec = self.coordinator.data.electricity
        attrs: dict[str, Any] = {"source": elec.source, "option": elec.option}
        if elec.option == OPTION_HPHC:
            off_peak = self.off_peak()
            attrs["period"] = None if off_peak is None else ("hc" if off_peak else "hp")
        if elec.valid_from:
            attrs["valid_from"] = elec.valid_from
        return attrs
