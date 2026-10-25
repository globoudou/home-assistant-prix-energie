"""Data update coordinator for Prix Énergie FR."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    CONF_WATER_PRICE,
    CONF_WATER_SUBSCRIPTION,
    DEFAULT_GAS_COEF,
    DOMAIN,
    ENERGY_ELEC,
    ENERGY_GAS,
    ENERGY_WATER,
    GAS_COOKING,
    OPTION_BASE,
    PRVG_PAGE,
    SOURCE_REGULATED,
    STORAGE_VERSION,
    TRVE_BASE_FALLBACK_CSV,
    TRVE_DATASET_API,
    UPDATE_INTERVAL,
)
from .parsers import (
    ParseError,
    classify_trve_resource,
    parse_prvg_html,
    parse_trve_csv,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)
HEADERS = {
    "User-Agent": "HomeAssistant-prix_energie (+https://github.com/globoudou/home-assistant-prix-energie)"
}


@dataclass
class ElecPrices:
    """Electricity prices in force (TTC)."""

    option: str
    subscription: float | None  # €/year
    base: float | None = None
    hp: float | None = None
    hc: float | None = None
    source: str = "custom"
    valid_from: str | None = None
    stale: bool = False


@dataclass
class GasPrices:
    """Gas prices in force (TTC)."""

    profile: str
    subscription: float | None  # €/year
    kwh: float | None
    kwh_per_m3: float
    source: str = "custom"
    period: str | None = None

    @property
    def m3(self) -> float | None:
        """Price per m³ using the conversion coefficient."""
        if self.kwh is None:
            return None
        return round(self.kwh * self.kwh_per_m3, 5)


@dataclass
class WaterPrices:
    """Water prices (TTC)."""

    m3: float | None
    subscription: float | None


@dataclass
class PriceData:
    """Everything the entities need."""

    electricity: ElecPrices | None = None
    gas: GasPrices | None = None
    water: WaterPrices | None = None
    errors: dict[str, str] | None = None


type PrixEnergieConfigEntry = ConfigEntry[PrixEnergieCoordinator]


class PrixEnergieCoordinator(DataUpdateCoordinator[PriceData]):
    """Fetch regulated prices and merge them with the user's settings."""

    config_entry: PrixEnergieConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PrixEnergieConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._cache: dict[str, Any] = {}
        self._cache_loaded = False

    @property
    def conf(self) -> dict[str, Any]:
        """Merged configuration (options override data)."""
        return {**self.config_entry.data, **self.config_entry.options}

    @property
    def energies(self) -> list[str]:
        """Configured energies."""
        return list(self.conf.get(CONF_ENERGIES, []))

    # ------------------------------------------------------------------ fetch
    async def _get_text(self, url: str) -> str:
        session = async_get_clientsession(self.hass)
        async with session.get(url, timeout=TIMEOUT, headers=HEADERS) as resp:
            resp.raise_for_status()
            raw = await resp.read()
        for encoding in ("utf-8", "cp1252", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    async def _get_json(self, url: str) -> Any:
        session = async_get_clientsession(self.hass)
        async with session.get(url, timeout=TIMEOUT, headers=HEADERS) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _fetch_trve(self, option: str, power: int, today: date) -> dict[str, Any]:
        """Return the TRVE row in force for an option and power."""
        urls: list[str] = []
        try:
            dataset = await self._get_json(TRVE_DATASET_API)
            resources = sorted(
                dataset.get("resources", []),
                key=lambda r: r.get("last_modified") or "",
                reverse=True,
            )
            for res in resources:
                if (res.get("format") or "").lower() not in ("csv", ""):
                    continue
                if classify_trve_resource(res.get("title", ""), res.get("url", "")) == option:
                    urls.append(res["url"])
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("data.gouv.fr dataset API failed: %s", err)
        if option == OPTION_BASE and TRVE_BASE_FALLBACK_CSV not in urls:
            urls.append(TRVE_BASE_FALLBACK_CSV)
        if not urls:
            raise UpdateFailed(f"no TRVE file found for option {option}")

        last_err: Exception | None = None
        for url in urls:
            try:
                parsed = parse_trve_csv(await self._get_text(url))
            except (aiohttp.ClientError, TimeoutError, ParseError) as err:
                last_err = err
                continue
            if parsed.option != option:
                continue
            found = parsed.in_effect(power, today)
            if found is None:
                raise UpdateFailed(f"power {power} kVA not in TRVE file (available: {parsed.powers()})")
            row, current = found
            return {
                "subscription": row.subscription,
                "base": row.base,
                "hp": row.hp,
                "hc": row.hc,
                "valid_from": row.start.isoformat(),
                "stale": not current,
                "fetched": dt_util.utcnow().isoformat(),
            }
        raise UpdateFailed(f"TRVE {option} download failed: {last_err}")

    async def _fetch_prvg(self, today: date) -> dict[str, Any]:
        grid = parse_prvg_html(await self._get_text(PRVG_PAGE), today)
        return {
            "cooking": [grid.cooking_subscription, grid.cooking_kwh],
            "heating": [grid.heating_subscription, grid.heating_kwh],
            "period": grid.period.isoformat() if grid.period else None,
            "fetched": dt_util.utcnow().isoformat(),
        }

    # ----------------------------------------------------------------- update
    async def _async_update_data(self) -> PriceData:
        if not self._cache_loaded:
            self._cache = await self._store.async_load() or {}
            self._cache_loaded = True

        conf = self.conf
        today = dt_util.now().date()
        errors: dict[str, str] = {}
        tasks: dict[str, Any] = {}

        if ENERGY_ELEC in self.energies and conf.get(CONF_ELEC_SOURCE) == SOURCE_REGULATED:
            option = conf.get(CONF_ELEC_OPTION, OPTION_BASE)
            power = int(conf.get(CONF_ELEC_POWER, 6))
            tasks[f"trve_{option}_{power}"] = self._fetch_trve(option, power, today)
        if ENERGY_GAS in self.energies and conf.get(CONF_GAS_SOURCE) == SOURCE_REGULATED:
            tasks["prvg"] = self._fetch_prvg(today)

        if tasks:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            changed = False
            for key, result in zip(tasks, results, strict=True):
                if isinstance(result, BaseException):
                    _LOGGER.warning("Update of %s failed: %s", key, result)
                    errors[key] = str(result)
                else:
                    self._cache[key] = result
                    changed = True
            if changed:
                await self._store.async_save(self._cache)

        data = PriceData(errors=errors or None)
        if ENERGY_ELEC in self.energies:
            data.electricity = self._elec_prices(conf)
        if ENERGY_GAS in self.energies:
            data.gas = self._gas_prices(conf)
        if ENERGY_WATER in self.energies:
            data.water = WaterPrices(
                m3=conf.get(CONF_WATER_PRICE),
                subscription=conf.get(CONF_WATER_SUBSCRIPTION),
            )

        missing = (
            data.electricity is not None
            and data.electricity.source == SOURCE_REGULATED
            and data.electricity.subscription is None
            and data.electricity.base is None
            and data.electricity.hp is None
        ) or (data.gas is not None and data.gas.source == SOURCE_REGULATED and data.gas.kwh is None)
        if missing and errors:
            raise UpdateFailed("; ".join(errors.values()))
        return data

    def _elec_prices(self, conf: dict[str, Any]) -> ElecPrices:
        option = conf.get(CONF_ELEC_OPTION, OPTION_BASE)
        if conf.get(CONF_ELEC_SOURCE) == SOURCE_REGULATED:
            power = int(conf.get(CONF_ELEC_POWER, 6))
            row = self._cache.get(f"trve_{option}_{power}") or {}
            return ElecPrices(
                option=option,
                subscription=row.get("subscription"),
                base=row.get("base"),
                hp=row.get("hp"),
                hc=row.get("hc"),
                source=SOURCE_REGULATED,
                valid_from=row.get("valid_from"),
                stale=bool(row.get("stale")),
            )
        return ElecPrices(
            option=option,
            subscription=conf.get(CONF_ELEC_SUBSCRIPTION),
            base=conf.get(CONF_ELEC_PRICE_BASE),
            hp=conf.get(CONF_ELEC_PRICE_HP),
            hc=conf.get(CONF_ELEC_PRICE_HC),
        )

    def _gas_prices(self, conf: dict[str, Any]) -> GasPrices:
        profile = conf.get(CONF_GAS_PROFILE, GAS_COOKING)
        coef = float(conf.get(CONF_GAS_COEF) or DEFAULT_GAS_COEF)
        if conf.get(CONF_GAS_SOURCE) == SOURCE_REGULATED:
            grid = self._cache.get("prvg") or {}
            sub, kwh = (grid.get(profile) or [None, None])[:2]
            return GasPrices(
                profile=profile,
                subscription=sub,
                kwh=kwh,
                kwh_per_m3=coef,
                source=SOURCE_REGULATED,
                period=grid.get("period"),
            )
        return GasPrices(
            profile=profile,
            subscription=conf.get(CONF_GAS_SUBSCRIPTION),
            kwh=conf.get(CONF_GAS_PRICE),
            kwh_per_m3=coef,
        )
