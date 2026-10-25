# Prix Énergie FR

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

Home Assistant integration that keeps **electricity, natural gas and water price sensors** up to date for France, ready to plug into the **Energy dashboard**.

| Energy | Source | Update |
|---|---|---|
| Electricity | French regulated tariff (*Tarif Bleu*, Base or Peak/Off-peak), CRE open data on [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/historique-des-tarifs-reglementes-de-vente-delectricite-pour-les-consommateurs-residentiels/) — or your own contract prices | every 6 h |
| Natural gas | CRE monthly gas reference price (*prix repère de vente de gaz*, GRDF area) from [cre.fr](https://www.cre.fr/consommateurs/prix-reperes-et-references/prix-repere-de-vente-de-gaz-naturel-a-destination-des-clients-residentiels.html) — or your own contract prices | every 6 h |
| Water | Your own price (there is no reliable national, up-to-date open data source per municipality) | — |

All prices are **all taxes included (TTC)**.

## Installation

### HACS (recommended)
1. HACS → ⋮ → *Custom repositories* → add `https://github.com/globoudou/home-assistant-prix-energie`, category **Integration**.
2. Install **Prix Énergie FR**, then restart Home Assistant.

### Manual
Copy `custom_components/prix_energie` into your `config/custom_components/` folder and restart.

## Configuration

*Settings → Devices & services → Add integration → Prix Énergie FR*

1. Choose a name and the energies to follow (electricity, gas, water).
2. **Electricity**
   - *Price source*: regulated tariff (automatic) or your own prices.
   - *Tariff option*: Base or Peak/Off-peak (HP/HC), and subscribed power (kVA).
   - *Off-peak hours*: e.g. `22:00-06:00` or `02:00-07:00, 13:00-16:00` (shown on your bill or Enedis account).
   - *Off-peak entity* (optional): an entity that tells which period is active, e.g. teleinfo `PTEC` (`HC..`/`HP..`), Linky standard `LTARF` (`HEURE CREUSE`…) or any binary sensor (`on` = off-peak). When available it takes precedence over the hours.
3. **Gas**
   - *Price source*: CRE reference price (automatic) or your own prices.
   - *Usage profile*: cooking / hot water (< 6,000 kWh/year) or heating.
   - *Conversion coefficient* (kWh/m³), printed on your bill, used for the €/m³ sensor.
4. **Water**: price per m³ and optional annual subscription.

Everything can be changed later with **Configure**.

## Entities

One device per energy.

| Entity | Unit | Notes |
|---|---|---|
| Electricity price | €/kWh | **Current** price (switches between HP and HC automatically) — use it in the Energy dashboard |
| Base price / Peak price / Off-peak price | €/kWh | depending on the option |
| Electricity subscription | € (per year) | attributes `per_month`, `per_day` |
| Off-peak hours (binary sensor) | — | HP/HC contracts only |
| Gas price | €/kWh | |
| Gas price per m³ | €/m³ | kWh price × conversion coefficient |
| Gas subscription | € (per year) | |
| Water price | €/m³ | |
| Water subscription | € (per year) | |

Useful attributes: `source`, `valid_from` (start date of the regulated tariff), `period` (gas grid month, or `hp`/`hc`), `stale` (no regulated row covers today yet — last known one is used), `last_errors`.

Prices are cached on disk: if data.gouv.fr or cre.fr is unreachable, sensors keep their last known value instead of becoming unavailable (which would break cost tracking).

## Energy dashboard

*Settings → Dashboards → Energy* (entity ids below are for an English installation; with Home Assistant in French they are named e.g. `sensor.<name>_electricite_prix_electricite`):

- **Electricity grid consumption** → *Use an entity with current price* → `sensor.<name>_electricity_price`.
- **Gas consumption** → *Use an entity with current price*:
  - gas meter in **m³** (e.g. Gazpar pulse counter) → `sensor.<name>_gas_price_per_m3`;
  - gas meter in **kWh** → `sensor.<name>_gas_price`.
- **Water consumption** (m³) → `sensor.<name>_water_price`.

The Energy dashboard only tracks consumption costs; subscriptions are exposed as separate sensors.

## Limitations

- Electricity regulated tariff: Base and HP/HC only (no Tempo), mainland France, ≤ 36 kVA.
- Gas: the CRE reference price is published for the GRDF area as an average grid; your supplier's price may differ (use *my own prices* if so).
- The CRE publishes the next month's gas grid in advance: the integration applies the grid of the current month and switches on the 1st (within a few hours).

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```

## License

MIT
