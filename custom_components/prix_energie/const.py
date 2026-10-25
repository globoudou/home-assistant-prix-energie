"""Constants for the Prix Énergie FR integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "prix_energie"
MANUFACTURER: Final = "Open data CRE / data.gouv.fr"

UPDATE_INTERVAL: Final = timedelta(hours=6)
STORAGE_VERSION: Final = 1

# --- Sources -----------------------------------------------------------------
# Dataset "Historique des tarifs réglementés de vente d'électricité pour les
# consommateurs résidentiels" (CRE) on data.gouv.fr. Resources are discovered
# through the data.gouv.fr API so a re-upload (new resource id) does not break
# the integration.
TRVE_DATASET_API: Final = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "historique-des-tarifs-reglementes-de-vente-delectricite-pour-les-consommateurs-residentiels/"
)
# Last-resort direct link to the "Option Base" CSV (known resource id).
TRVE_BASE_FALLBACK_CSV: Final = "https://www.data.gouv.fr/fr/datasets/r/c13d05e5-9e55-4d03-bf7e-042a2ade7e49"
# Monthly gas reference price (prix repère de vente de gaz naturel, GRDF zone).
PRVG_PAGE: Final = (
    "https://www.cre.fr/consommateurs/prix-reperes-et-references/"
    "prix-repere-de-vente-de-gaz-naturel-a-destination-des-clients-residentiels.html"
)

# --- Config keys -------------------------------------------------------------
CONF_ENERGIES: Final = "energies"
ENERGY_ELEC: Final = "electricity"
ENERGY_GAS: Final = "gas"
ENERGY_WATER: Final = "water"

# Electricity
CONF_ELEC_OPTION: Final = "elec_option"
OPTION_BASE: Final = "base"
OPTION_HPHC: Final = "hphc"
CONF_ELEC_POWER: Final = "elec_power_kva"
CONF_ELEC_SOURCE: Final = "elec_source"
CONF_ELEC_SUBSCRIPTION: Final = "elec_custom_subscription"
CONF_ELEC_PRICE_BASE: Final = "elec_custom_base"
CONF_ELEC_PRICE_HP: Final = "elec_custom_hp"
CONF_ELEC_PRICE_HC: Final = "elec_custom_hc"
CONF_HC_SCHEDULE: Final = "hc_schedule"
CONF_HC_ENTITY: Final = "hc_entity"

# Gas
CONF_GAS_PROFILE: Final = "gas_profile"
GAS_COOKING: Final = "cooking"
GAS_HEATING: Final = "heating"
CONF_GAS_SOURCE: Final = "gas_source"
CONF_GAS_SUBSCRIPTION: Final = "gas_custom_subscription"
CONF_GAS_PRICE: Final = "gas_custom_kwh"
CONF_GAS_COEF: Final = "gas_kwh_per_m3"

# Water
CONF_WATER_PRICE: Final = "water_price_m3"
CONF_WATER_SUBSCRIPTION: Final = "water_subscription"

SOURCE_REGULATED: Final = "regulated"  # TRVE (elec) / PRVG (gas)
SOURCE_CUSTOM: Final = "custom"

POWERS_KVA: Final = [3, 6, 9, 12, 15, 18, 24, 30, 36]

DEFAULT_HC_SCHEDULE: Final = "22:00-06:00"
DEFAULT_GAS_COEF: Final = 11.2
