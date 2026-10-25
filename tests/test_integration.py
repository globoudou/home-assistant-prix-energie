"""Config flow and setup tests."""

from datetime import datetime

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.prix_energie.const import DOMAIN, PRVG_PAGE, TRVE_DATASET_API

from .fixtures import DATASET_JSON, PRVG_HTML, TRVE_BASE_CSV, TRVE_HPHC_CSV

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _mock_sources(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(TRVE_DATASET_API, json=DATASET_JSON)
    aioclient_mock.get("https://example.test/base.csv", text=TRVE_BASE_CSV)
    aioclient_mock.get("https://example.test/hphc.csv", text=TRVE_HPHC_CSV)
    aioclient_mock.get(PRVG_PAGE, text=PRVG_HTML)


async def test_full_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    """Configure all three energies, check sensors and HC switching."""
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to(datetime(2026, 10, 25, 21, 59, 0, tzinfo=dt_util.get_time_zone("Europe/Paris")))
    _mock_sources(aioclient_mock)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Maison", "energies": ["electricity", "gas", "water"]}
    )
    assert result["step_id"] == "electricity"
    # invalid schedule
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"elec_source": "regulated", "elec_option": "hphc", "elec_power_kva": "6", "hc_schedule": "nope"},
    )
    assert result["errors"] == {"hc_schedule": "invalid_schedule"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "elec_source": "regulated",
            "elec_option": "hphc",
            "elec_power_kva": "6",
            "hc_schedule": "22:00-06:00",
        },
    )
    assert result["step_id"] == "gas"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"gas_source": "regulated", "gas_profile": "heating", "gas_kwh_per_m3": 11.2}
    )
    assert result["step_id"] == "water"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"water_price_m3": 4.34, "water_subscription": 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["elec_power_kva"] == 6
    await hass.async_block_till_done()

    def val(eid):
        return hass.states.get(eid).state

    assert val("sensor.maison_electricite_electricity_price") == "0.2068"  # 21:59 -> HP
    assert val("sensor.maison_electricite_off_peak_price") == "0.162"
    assert val("sensor.maison_electricite_electricity_subscription") == "201.48"
    assert val("binary_sensor.maison_electricite_off_peak_hours") == "off"
    assert val("sensor.maison_gaz_naturel_gas_price") == "0.155"
    assert float(val("sensor.maison_gaz_naturel_gas_price_per_m3")) == pytest.approx(0.155 * 11.2)
    assert val("sensor.maison_eau_water_price") == "4.34"
    assert hass.states.get("sensor.maison_gaz_naturel_gas_price").attributes["period"] == "2026-10-01"

    freezer.tick(61)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert val("sensor.maison_electricite_electricity_price") == "0.162"
    assert val("binary_sensor.maison_electricite_off_peak_hours") == "on"


async def test_cache_survives_outage(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Prices stay available when sources fail after a first success."""
    _mock_sources(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Maison",
        data={
            "energies": ["electricity"],
            "elec_source": "regulated",
            "elec_option": "base",
            "elec_power_kva": 6,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.maison_electricite_electricity_price").state == "0.194"

    aioclient_mock.clear_requests()
    aioclient_mock.get(TRVE_DATASET_API, status=500)
    aioclient_mock.get(
        "https://www.data.gouv.fr/fr/datasets/r/c13d05e5-9e55-4d03-bf7e-042a2ade7e49", status=500
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.maison_electricite_electricity_price")
    assert state.state == "0.194"
    assert "last_errors" in hass.states.get("sensor.maison_electricite_base_price").attributes


async def test_not_ready_without_data(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """No data at all -> setup retried later."""
    aioclient_mock.get(TRVE_DATASET_API, status=500)
    aioclient_mock.get(
        "https://www.data.gouv.fr/fr/datasets/r/c13d05e5-9e55-4d03-bf7e-042a2ade7e49", status=500
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="X",
        data={
            "energies": ["electricity"],
            "elec_source": "regulated",
            "elec_option": "base",
            "elec_power_kva": 6,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_custom_prices_and_options(hass: HomeAssistant) -> None:
    """Custom prices need no network; options flow updates them."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Maison",
        data={
            "energies": ["electricity"],
            "elec_source": "custom",
            "elec_option": "base",
            "elec_power_kva": 6,
            "elec_custom_base": 0.1952,
            "elec_custom_subscription": 180,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.maison_electricite_electricity_price").state == "0.1952"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"energies": ["electricity", "water"]}
    )
    assert result["step_id"] == "electricity"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"elec_source": "custom", "elec_option": "base", "elec_power_kva": "6", "elec_custom_base": 0.21},
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"water_price_m3": 3.9})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.maison_electricite_electricity_price").state == "0.21"
    assert hass.states.get("sensor.maison_eau_water_price").state == "3.9"
    # subscription cleared in the form -> removed
    assert hass.states.get("sensor.maison_electricite_electricity_subscription").state == "unavailable"


async def test_card_is_served(hass: HomeAssistant) -> None:
    """The Lovelace card is registered as a static path and an extra module."""
    from unittest.mock import AsyncMock, MagicMock, patch

    hass.config.components.add("frontend")
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
        from homeassistant.setup import async_setup_component

        assert await async_setup_component(hass, DOMAIN, {})
    config = hass.http.async_register_static_paths.call_args[0][0][0]
    assert config.url_path == "/prix_energie/prix-energie-card.js"
    assert config.path.endswith("frontend/prix-energie-card.js")
    assert add_js.call_args[0][1] == "/prix_energie/prix-energie-card.js?v=1.1.0"
