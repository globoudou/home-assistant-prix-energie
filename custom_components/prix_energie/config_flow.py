"""Config and options flow for Prix Énergie FR."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ELEC_OPTION,
    CONF_ELEC_POWER,
    CONF_ELEC_PRICE_BASE,
    CONF_ELEC_PRICE_HC,
    CONF_ELEC_PRICE_HP,
    CONF_ELEC_SOURCE,
    CONF_ELEC_SUBSCRIPTION,
    CONF_ENERGIES,
    CONF_GAS_COEF,
    CONF_GAS_PRICE,
    CONF_GAS_PROFILE,
    CONF_GAS_SOURCE,
    CONF_GAS_SUBSCRIPTION,
    CONF_HC_ENTITY,
    CONF_HC_SCHEDULE,
    CONF_WATER_PRICE,
    CONF_WATER_SUBSCRIPTION,
    DEFAULT_GAS_COEF,
    DEFAULT_HC_SCHEDULE,
    DOMAIN,
    ENERGY_ELEC,
    ENERGY_GAS,
    ENERGY_WATER,
    GAS_COOKING,
    GAS_HEATING,
    OPTION_BASE,
    OPTION_HPHC,
    POWERS_KVA,
    SOURCE_CUSTOM,
    SOURCE_REGULATED,
)
from .schedule import ScheduleError, parse_schedule

ENERGY_STEPS = (ENERGY_ELEC, ENERGY_GAS, ENERGY_WATER)


def _select(options: list[str], key: str, multiple: bool = False) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            translation_key=key,
            multiple=multiple,
            mode=selector.SelectSelectorMode.LIST,
        )
    )


def _number(step: float | str, unit: str, maximum: float = 10000) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=maximum, step=step, unit_of_measurement=unit, mode=selector.NumberSelectorMode.BOX
        )
    )


def _opt(key: str, defaults: dict[str, Any]) -> vol.Optional:
    """Optional field pre-filled only when a value exists."""
    if defaults.get(key) is not None:
        return vol.Optional(key, description={"suggested_value": defaults[key]})
    return vol.Optional(key)


def _energies_schema(d: dict[str, Any]) -> dict:
    return {
        vol.Required(CONF_ENERGIES, default=d.get(CONF_ENERGIES, [ENERGY_ELEC])): _select(
            list(ENERGY_STEPS), CONF_ENERGIES, multiple=True
        )
    }


def _elec_schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ELEC_SOURCE, default=d.get(CONF_ELEC_SOURCE, SOURCE_REGULATED)): _select(
                [SOURCE_REGULATED, SOURCE_CUSTOM], CONF_ELEC_SOURCE
            ),
            vol.Required(CONF_ELEC_OPTION, default=d.get(CONF_ELEC_OPTION, OPTION_BASE)): _select(
                [OPTION_BASE, OPTION_HPHC], CONF_ELEC_OPTION
            ),
            vol.Required(CONF_ELEC_POWER, default=str(d.get(CONF_ELEC_POWER, 6))): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[str(p) for p in POWERS_KVA], mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional(CONF_HC_SCHEDULE, default=d.get(CONF_HC_SCHEDULE, DEFAULT_HC_SCHEDULE)): str,
            _opt(CONF_HC_ENTITY, d): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor", "input_boolean"])
            ),
            _opt(CONF_ELEC_SUBSCRIPTION, d): _number(0.01, "€/an"),
            _opt(CONF_ELEC_PRICE_BASE, d): _number("any", "€/kWh", 5),
            _opt(CONF_ELEC_PRICE_HP, d): _number("any", "€/kWh", 5),
            _opt(CONF_ELEC_PRICE_HC, d): _number("any", "€/kWh", 5),
        }
    )


def _gas_schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_GAS_SOURCE, default=d.get(CONF_GAS_SOURCE, SOURCE_REGULATED)): _select(
                [SOURCE_REGULATED, SOURCE_CUSTOM], CONF_GAS_SOURCE
            ),
            vol.Required(CONF_GAS_PROFILE, default=d.get(CONF_GAS_PROFILE, GAS_HEATING)): _select(
                [GAS_COOKING, GAS_HEATING], CONF_GAS_PROFILE
            ),
            vol.Required(CONF_GAS_COEF, default=d.get(CONF_GAS_COEF, DEFAULT_GAS_COEF)): _number(
                0.01, "kWh/m³", 20
            ),
            _opt(CONF_GAS_SUBSCRIPTION, d): _number(0.01, "€/an"),
            _opt(CONF_GAS_PRICE, d): _number("any", "€/kWh", 5),
        }
    )


def _water_schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_WATER_PRICE, description={"suggested_value": d.get(CONF_WATER_PRICE)}): _number(
                "any", "€/m³", 50
            ),
            _opt(CONF_WATER_SUBSCRIPTION, d): _number(0.01, "€/an"),
        }
    )


def _validate_elec(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if data.get(CONF_ELEC_OPTION) == OPTION_HPHC and not data.get(CONF_HC_ENTITY):
        try:
            parse_schedule(data.get(CONF_HC_SCHEDULE) or "")
        except ScheduleError:
            errors[CONF_HC_SCHEDULE] = "invalid_schedule"
    if data.get(CONF_ELEC_SOURCE) == SOURCE_CUSTOM:
        if data.get(CONF_ELEC_OPTION) == OPTION_BASE and data.get(CONF_ELEC_PRICE_BASE) is None:
            errors[CONF_ELEC_PRICE_BASE] = "price_required"
        if data.get(CONF_ELEC_OPTION) == OPTION_HPHC:
            for key in (CONF_ELEC_PRICE_HP, CONF_ELEC_PRICE_HC):
                if data.get(key) is None:
                    errors[key] = "price_required"
    return errors


def _validate_gas(data: dict[str, Any]) -> dict[str, str]:
    if data.get(CONF_GAS_SOURCE) == SOURCE_CUSTOM and data.get(CONF_GAS_PRICE) is None:
        return {CONF_GAS_PRICE: "price_required"}
    if not data.get(CONF_GAS_COEF):
        return {CONF_GAS_COEF: "invalid_coef"}
    return {}


class _StepsMixin:
    """Electricity / gas / water steps shared by config and options flows."""

    _data: dict[str, Any]

    def _next_energy(self, after: str | None) -> str | None:
        selected = self._data.get(CONF_ENERGIES, [])
        order = list(ENERGY_STEPS)
        start = order.index(after) + 1 if after else 0
        for energy in order[start:]:
            if energy in selected:
                return energy
        return None

    async def _goto(self, after: str | None) -> ConfigFlowResult:
        nxt = self._next_energy(after)
        if nxt is None:
            return await self._async_finish()
        return await getattr(self, f"async_step_{nxt}")()

    async def _async_finish(self) -> ConfigFlowResult:  # pragma: no cover - overridden
        raise NotImplementedError

    @staticmethod
    def _clean(user_input: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        """Normalise and drop empty optional fields."""
        out = {k: v for k, v in user_input.items() if v not in ("", None)}
        if CONF_ELEC_POWER in out:
            out[CONF_ELEC_POWER] = int(out[CONF_ELEC_POWER])
        for key in keys:
            if key not in out:
                out[key] = None
        return out

    async def async_step_electricity(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Electricity settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = self._clean(
                user_input,
                (
                    CONF_HC_ENTITY,
                    CONF_ELEC_SUBSCRIPTION,
                    CONF_ELEC_PRICE_BASE,
                    CONF_ELEC_PRICE_HP,
                    CONF_ELEC_PRICE_HC,
                ),
            )
            errors = _validate_elec(data)
            if not errors:
                self._data.update(data)
                return await self._goto(ENERGY_ELEC)
            defaults = {**self._data, **data}
        else:
            defaults = self._data
        return self.async_show_form(step_id=ENERGY_ELEC, data_schema=_elec_schema(defaults), errors=errors)

    async def async_step_gas(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Gas settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = self._clean(user_input, (CONF_GAS_SUBSCRIPTION, CONF_GAS_PRICE))
            errors = _validate_gas(data)
            if not errors:
                self._data.update(data)
                return await self._goto(ENERGY_GAS)
            defaults = {**self._data, **data}
        else:
            defaults = self._data
        return self.async_show_form(step_id=ENERGY_GAS, data_schema=_gas_schema(defaults), errors=errors)

    async def async_step_water(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Water settings."""
        if user_input is not None:
            self._data.update(self._clean(user_input, (CONF_WATER_SUBSCRIPTION,)))
            return await self._goto(ENERGY_WATER)
        return self.async_show_form(step_id=ENERGY_WATER, data_schema=_water_schema(self._data))


class PrixEnergieConfigFlow(_StepsMixin, ConfigFlow, domain=DOMAIN):
    """Initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._title = "Prix énergie"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name and energies."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_ENERGIES):
                errors[CONF_ENERGIES] = "no_energy"
            else:
                self._title = user_input.get(CONF_NAME) or self._title
                self._data[CONF_ENERGIES] = user_input[CONF_ENERGIES]
                return await self._goto(None)
        schema = vol.Schema(
            {vol.Required(CONF_NAME, default=self._title): str, **_energies_schema(self._data)}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def _async_finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title=self._title, data=self._data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options flow."""
        return PrixEnergieOptionsFlow()


class PrixEnergieOptionsFlow(_StepsMixin, OptionsFlow):
    """Change prices and settings later."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Energies selection."""
        if not self._data:
            self._data = {**self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_ENERGIES):
                errors[CONF_ENERGIES] = "no_energy"
            else:
                self._data[CONF_ENERGIES] = user_input[CONF_ENERGIES]
                return await self._goto(None)
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(_energies_schema(self._data)), errors=errors
        )

    async def _async_finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._data)
