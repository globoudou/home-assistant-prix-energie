/*
 * Prix Énergie FR — simple Lovelace card.
 *
 *   type: custom:prix-energie-card
 *   title: Prix de l'énergie        # optional
 *   energies: [electricity, gas, water]   # optional filter / order
 *   show_subscription: true         # optional
 */

const PLATFORM = "prix_energie";
const VERSION = "1.1.0";

const I18N = {
  fr: {
    title: "Prix de l'énergie",
    electricity: "Électricité",
    gas: "Gaz",
    water: "Eau",
    now: "Maintenant",
    hp: "Heures pleines",
    hc: "Heures creuses",
    base: "Base",
    sub: "Abonnement",
    perMonth: "/mois",
    since: "en vigueur depuis le",
    regulated: "Tarif réglementé",
    reference: "Prix repère CRE",
    custom: "Prix personnalisés",
    stale: "Tarif possiblement périmé",
    error: "Dernière mise à jour en échec",
    none: "Aucune entité Prix Énergie FR trouvée.",
  },
  en: {
    title: "Energy prices",
    electricity: "Electricity",
    gas: "Gas",
    water: "Water",
    now: "Now",
    hp: "Peak",
    hc: "Off-peak",
    base: "Base",
    sub: "Subscription",
    perMonth: "/month",
    since: "in force since",
    regulated: "Regulated tariff",
    reference: "CRE reference price",
    custom: "Custom prices",
    stale: "Tariff may be outdated",
    error: "Last update failed",
    none: "No Prix Énergie FR entity found.",
  },
};

const ICONS = { electricity: "mdi:flash", gas: "mdi:fire", water: "mdi:water" };
const ENERGY_KEYS = {
  electricity: [
    "electricity_price",
    "electricity_price_base",
    "electricity_price_hp",
    "electricity_price_hc",
    "electricity_subscription",
    "off_peak",
  ],
  gas: ["gas_price_kwh", "gas_price_m3", "gas_subscription"],
  water: ["water_price", "water_subscription"],
};

function energyOf(key) {
  return Object.keys(ENERGY_KEYS).find((e) => ENERGY_KEYS[e].includes(key));
}

class PrixEnergieCard extends HTMLElement {
  static getStubConfig() {
    return { show_subscription: true };
  }

  setConfig(config) {
    this._config = { show_subscription: true, ...config };
    this._signature = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const groups = this._groups();
    const signature = JSON.stringify(
      groups.map((g) =>
        Object.values(g.entities).map((id) => {
          const s = hass.states[id];
          return s ? [s.state, s.last_updated] : null;
        })
      )
    ) + hass.language;
    if (signature === this._signature) return;
    this._signature = signature;
    this._render(groups);
  }

  getCardSize() {
    return 2 + this._groups().length * 2;
  }

  get _t() {
    const lang = (this._hass && this._hass.language) || "en";
    return I18N[lang.split("-")[0]] || I18N.en;
  }

  /** Group the integration's entities by device (one device per energy). */
  _groups() {
    if (!this._hass || !this._hass.entities) return [];
    const wanted = this._config.energies;
    const byDevice = {};
    for (const entry of Object.values(this._hass.entities)) {
      if (entry.platform !== PLATFORM || !entry.translation_key) continue;
      const energy = energyOf(entry.translation_key);
      if (!energy || (wanted && !wanted.includes(energy))) continue;
      const dev = entry.device_id || energy;
      byDevice[dev] = byDevice[dev] || { device: dev, energy, entities: {} };
      byDevice[dev].entities[entry.translation_key] = entry.entity_id;
    }
    const order = wanted || Object.keys(ENERGY_KEYS);
    return Object.values(byDevice).sort(
      (a, b) => order.indexOf(a.energy) - order.indexOf(b.energy)
    );
  }

  _state(id) {
    return id ? this._hass.states[id] : undefined;
  }

  _num(id, digits = 4) {
    const s = this._state(id);
    if (!s || isNaN(parseFloat(s.state))) return "—";
    return new Intl.NumberFormat(this._hass.locale?.language || this._hass.language, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(parseFloat(s.state));
  }

  _unit(id) {
    const s = this._state(id);
    return (s && s.attributes.unit_of_measurement) || "";
  }

  _date(iso, monthOnly = false) {
    if (!iso) return "";
    const d = new Date(iso + "T00:00:00");
    const opts = monthOnly
      ? { month: "long", year: "numeric" }
      : { day: "numeric", month: "long", year: "numeric" };
    return d.toLocaleDateString(this._hass.language, opts);
  }

  _value(id, digits, cls = "") {
    if (!id) return "";
    return `<span class="value ${cls}" data-entity="${id}">${this._num(id, digits)}<span class="unit"> ${this._unit(id)}</span></span>`;
  }

  _subscription(id) {
    const s = this._state(id);
    if (!this._config.show_subscription || !s || s.attributes.per_month === undefined) return "";
    const fmt = new Intl.NumberFormat(this._hass.language, { style: "currency", currency: "EUR" });
    return `<div class="row sub" data-entity="${id}"><span>${this._t.sub}</span><span>${fmt.format(
      s.attributes.per_month
    )}${this._t.perMonth}</span></div>`;
  }

  _footer(id, energy) {
    const s = this._state(id);
    if (!s) return "";
    const a = s.attributes;
    const t = this._t;
    const bits = [];
    if (a.source === "regulated") bits.push(energy === "gas" ? t.reference : t.regulated);
    else if (a.source === "custom") bits.push(t.custom);
    if (a.valid_from) bits.push(`${t.since} ${this._date(a.valid_from)}`);
    if (a.period && /^\d{4}-\d{2}-\d{2}$/.test(a.period))
      bits.push(this._date(a.period, true));
    let html = bits.length ? `<div class="meta">${bits.join(" · ")}</div>` : "";
    if (a.stale) html += `<div class="warn"><ha-icon icon="mdi:alert"></ha-icon>${t.stale}</div>`;
    if (a.last_errors) html += `<div class="warn"><ha-icon icon="mdi:cloud-alert"></ha-icon>${t.error}</div>`;
    return html;
  }

  _electricity(e) {
    const t = this._t;
    const cur = this._state(e.electricity_price);
    const period = cur && cur.attributes.period;
    let detail = "";
    if (e.electricity_price_hp) {
      detail = `
        <div class="pills">
          <div class="pill ${period === "hp" ? "active" : ""}" data-entity="${e.electricity_price_hp}">
            <ha-icon icon="mdi:weather-sunny"></ha-icon><span>${t.hp}</span>${this._value(e.electricity_price_hp, 4)}
          </div>
          <div class="pill ${period === "hc" ? "active" : ""}" data-entity="${e.electricity_price_hc}">
            <ha-icon icon="mdi:weather-night"></ha-icon><span>${t.hc}</span>${this._value(e.electricity_price_hc, 4)}
          </div>
        </div>`;
    }
    const badge = period ? `<span class="badge ${period}">${period === "hc" ? t.hc : t.hp}</span>` : "";
    return `
      <div class="main">
        <span class="label">${t.now}</span>${badge}
        ${this._value(e.electricity_price, 4, "big")}
      </div>
      ${detail}
      ${this._subscription(e.electricity_subscription)}
      ${this._footer(e.electricity_price, "electricity")}`;
  }

  _gas(e) {
    return `
      <div class="main">
        ${this._value(e.gas_price_kwh, 4, "big")}
        ${this._value(e.gas_price_m3, 4, "second")}
      </div>
      ${this._subscription(e.gas_subscription)}
      ${this._footer(e.gas_price_kwh, "gas")}`;
  }

  _water(e) {
    return `
      <div class="main">${this._value(e.water_price, 2, "big")}</div>
      ${this._subscription(e.water_subscription)}`;
  }

  _render(groups = this._groups()) {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const t = this._t;
    const showDeviceName = new Set(groups.map((g) => g.energy)).size !== groups.length;
    const sections = groups
      .map((g) => {
        const dev = this._hass.devices && this._hass.devices[g.device];
        const name = showDeviceName && dev ? dev.name_by_user || dev.name : t[g.energy];
        const body = this[`_${g.energy}`](g.entities);
        return `
          <div class="section ${g.energy}">
            <div class="head"><ha-icon icon="${ICONS[g.energy]}"></ha-icon><span>${name}</span></div>
            ${body}
          </div>`;
      })
      .join("");
    const title = this._config.title === undefined ? t.title : this._config.title;

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        .title { font-size: 1.25em; font-weight: 500; margin-bottom: 8px; }
        .section { padding: 10px 0; border-top: 1px solid var(--divider-color); }
        .sections > .section:first-child { border-top: none; padding-top: 0; }
        .head { display: flex; align-items: center; gap: 8px; font-weight: 500; color: var(--secondary-text-color); }
        .electricity .head ha-icon { color: var(--energy-grid-consumption-color, #488fc2); }
        .gas .head ha-icon { color: var(--energy-gas-color, #8e021b); }
        .water .head ha-icon { color: var(--energy-water-color, #00bcd4); }
        .main { display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px; margin: 6px 0; }
        .label { color: var(--secondary-text-color); }
        .value { cursor: pointer; white-space: nowrap; }
        .value.big { font-size: 1.9em; font-weight: 500; margin-left: auto; }
        .value.second { color: var(--secondary-text-color); margin-left: 8px; }
        .gas .value.big, .water .value.big { margin-left: 0; }
        .unit { font-size: 0.55em; color: var(--secondary-text-color); font-weight: 400; }
        .value:not(.big) .unit { font-size: 0.85em; }
        .badge { font-size: 0.75em; padding: 2px 8px; border-radius: 10px; color: #fff; }
        .badge.hp { background: var(--warning-color, #ff9800); }
        .badge.hc { background: var(--info-color, #039be5); }
        .pills { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 6px 0; }
        .pill { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; padding: 8px;
                border-radius: 10px; background: var(--secondary-background-color); cursor: pointer;
                border: 2px solid transparent; font-size: 0.9em; }
        .pill.active { border-color: var(--primary-color); }
        .pill ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); }
        .row { display: flex; justify-content: space-between; cursor: pointer; padding: 2px 0; }
        .sub span:first-child { color: var(--secondary-text-color); }
        .meta { font-size: 0.8em; color: var(--secondary-text-color); margin-top: 4px; }
        .warn { display: flex; align-items: center; gap: 4px; font-size: 0.8em; color: var(--warning-color, #ff9800); margin-top: 4px; }
        .warn ha-icon { --mdc-icon-size: 16px; }
        .empty { color: var(--secondary-text-color); }
      </style>
      <ha-card>
        ${title ? `<div class="title">${title}</div>` : ""}
        <div class="sections">${sections || `<div class="empty">${t.none}</div>`}</div>
      </ha-card>`;

    this.shadowRoot.querySelectorAll("[data-entity]").forEach((el) =>
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const event = new Event("hass-more-info", { bubbles: true, composed: true });
        event.detail = { entityId: el.dataset.entity };
        this.dispatchEvent(event);
      })
    );
  }
}

if (!customElements.get("prix-energie-card")) {
  customElements.define("prix-energie-card", PrixEnergieCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "prix-energie-card",
    name: "Prix Énergie FR",
    description: "Prix de l'électricité (HP/HC), du gaz et de l'eau",
    preview: true,
  });
  console.info(`%c PRIX-ENERGIE-CARD %c ${VERSION} `, "background:#488fc2;color:#fff", "");
}
