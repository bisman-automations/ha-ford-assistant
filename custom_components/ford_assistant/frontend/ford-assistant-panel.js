/*
 * Ford Assistant sidebar dashboard.
 *
 * A plain web component (no build step, no external libraries) that Home
 * Assistant loads as a custom panel. It asks the backend once for the vehicles
 * and their entity IDs (`ford_assistant/vehicles`), then renders from the live
 * `hass` object it's given and calls services through it.
 */

const STORAGE_KEY = "ford-assistant-panel:vehicle";

// Whether the page can't be seen (another tab, or a screen that's off).
function pageHidden() {
  return typeof document !== "undefined" && Boolean(document.hidden);
}
const PENDING_TIMEOUT = 45000; // Ford commands can take 30+ seconds
// Locking waits for the vehicle to report back, which can take longer.
const LOCK_TIMEOUT = 90000;
// What the lock reports once a command has really finished.
const LOCK_DONE = { lock: "locked", unlock: "unlocked" };
const PENDING_LABELS = { lock: "locking", unlock: "unlocking" };
const BAD = new Set(["unknown", "unavailable", "", null, undefined]);
// Dashboard buttons and the action the current driving mode can block.
const ACTION_BLOCKS = {
  lock: "lock",
  unlock: "unlock",
  start: "remote_start",
  stop: "remote_start",
  extend: "remote_start",
  honk: "honk",
  garage_open: "garage_open",
  garage_close: "garage_close",
};

const FEATURE_GROUPS = [
  { title: "security", keys: ["auto_lock", "night_lock", "door_open_alert", "alarm_alert"] },
  {
    title: "remote_start",
    keys: ["precondition", "work_prompt", "auto_extend", "remote_start_activity"],
  },
  {
    title: "alerts",
    keys: [
      "fuel_alert",
      "oil_alert",
      "battery_alert",
      "tire_alert",
      "indicator_alert",
      "windows_alert",
      "charge_alert",
      "plug_in_reminder",
    ],
  },
  { title: "garage", keys: ["garage_open", "garage_close"] },
  { title: "notifications", keys: ["status_activity", "quiet_hours", "clear_resolved"] },
];

const TIRES = [
  ["frontLeft", "FL"],
  ["frontRight", "FR"],
  ["rearLeft", "RL"],
  ["rearRight", "RR"],
];

// The dashboard's words, by language (Home Assistant's language for the
// person viewing it). Anything missing falls back to English. To add a
// language, copy the "en" block and translate the values, keeping every
// {placeholder}; notifications are in ../messages.py.
const WORDS = {
  en: {
    loading: "Loading your vehicles",
    load_failed: "Couldn't load your vehicles",
    try_again: "Try again",
    no_vehicles: "No vehicles yet",
    no_vehicles_text: "Add Ford Assistant for a vehicle from the Ford integration to see it here.",
    open_integration: "Open Ford Assistant",
    denied_title: "You don't have access to Ford Assistant",
    denied_text: "Ask an admin to give you access. They can do it at the bottom of this dashboard.",
    access_title: "Who can use Ford Assistant",
    access_text: "Admins always can. So can a household driver whose person is linked to their Home Assistant user. Anyone else only sees it if you check them here.",
    access_all_admins: "Everyone with a Home Assistant login is an admin.",
    access_sidebar: "Home Assistant can't show a sidebar entry to only some people, so everyone sees Ford Assistant in the sidebar. People who aren't checked get a page saying they don't have access.",
    access_saved: "Access saved",
    whos_driving: "Who's driving",
    mode_household: "Household",
    mode_service: "Service",
    mode_guest: "Guest",
    nobody: "Nobody",
    automations_suppressed: "Ford Assistant is holding some actions for this mode.",
    reverts_at: "Back to Household at {time}",
    action_blocked: "That action is blocked while this mode is on.",
    // Status
    alarm_going: "Alarm!",
    locking: "Locking…",
    unlocking: "Unlocking…",
    lock_jammed: "Lock jammed",
    running: "Running",
    driving: "Driving",
    door_open: "Door open",
    unlocked: "Unlocked",
    locked: "Locked",
    parked: "Parked",
    // Location
    unknown: "Unknown",
    home: "Home",
    away: "Away",
    // Buttons
    lock: "Lock",
    unlock: "Unlock",
    start: "Start",
    stop: "Stop",
    extend: "Extend",
    honk: "Honk & flash",
    garage_open: "Open garage",
    garage_close: "Close garage",
    refresh: "Refresh",
    sending: "Sending…",
    failed: "Couldn't {action}: {error}",
    // Tiles
    fuel: "Fuel",
    battery: "Battery",
    range: "{range} {unit} range",
    charging: "Charging",
    remote_start: "Remote start",
    min_left: "{minutes} min left",
    doors: "Doors",
    n_open: "{count} open",
    all_closed: "All closed",
    windows: "Windows",
    location: "Location",
    tire_pressure: "Tire pressure",
    oil_life: "Oil life",
    battery_12v: "12V battery",
    alarm: "Alarm",
    warning_lights: "Warning lights",
    n_on: "{count} on",
    none: "None",
    outside: "Outside",
    odometer: "Odometer",
    // Settings
    security: "Security",
    alerts: "Alerts",
    garage: "Garage",
    notifications: "Notifications",
    thresholds: "Thresholds & times",
    // Confirmations
    cancel: "Cancel",
    confirm_unlock_title: "Unlock {name}?",
    confirm_unlock_text: "All doors will unlock.",
    confirm_start_title: "Start {name}?",
    confirm_start_text: "The engine will start remotely and run until the timer ends or you stop it.",
    confirm_garage_title: "Open the garage?",
    confirm_garage_text: "The garage door will open.",
    open: "Open",
    // Readings from the Ford integration (others are spelled out)
    value_Open: "Open",
    value_Closed: "Closed",
    value_ARMED: "Armed",
    value_PREARMED: "Arming",
    value_DISARMED: "Disarmed",
    value_TRIGGERED: "Triggered",
    value_CONNECTED: "Plugged in",
    value_DISCONNECTED: "Unplugged",
    value_STOPPED: "Stopped",
    value_COMPLETED: "Done",
    value_FAULT: "Fault",
    value_STATION_NOT_DETECTED: "Charger not found",
    door_hood: "Hood",
    door_tailgate: "Tailgate",
    door_innerTailgate: "Inner tailgate",
    door_driverFront: "Driver front",
    door_passengerFront: "Passenger front",
    door_driverRear: "Driver rear",
    door_passengerRear: "Passenger rear",
    tire_FL: "FL",
    tire_FR: "FR",
    tire_RL: "RL",
    tire_RR: "RR",
  },
  fr: {
    loading: "Chargement de vos véhicules",
    load_failed: "Impossible de charger vos véhicules",
    try_again: "Réessayer",
    no_vehicles: "Aucun véhicule pour l'instant",
    no_vehicles_text: "Ajoutez Ford Assistant pour un véhicule de l'intégration Ford pour le voir ici.",
    open_integration: "Ouvrir Ford Assistant",
    denied_title: "Vous n'avez pas accès à Ford Assistant",
    denied_text: "Demandez l'accès à un administrateur. Il peut le donner en bas de ce tableau de bord.",
    access_title: "Qui peut utiliser Ford Assistant",
    access_text: "Les administrateurs le peuvent toujours, ainsi qu'un conducteur du foyer dont la personne est liée à son compte Home Assistant. Les autres ne le voient que si vous les cochez ici.",
    access_all_admins: "Toutes les personnes ayant un compte Home Assistant sont administrateurs.",
    access_sidebar: "Home Assistant ne peut pas afficher une entrée de la barre latérale pour certaines personnes seulement : tout le monde voit Ford Assistant dans la barre latérale. Les personnes non cochées voient une page indiquant qu'elles n'y ont pas accès.",
    access_saved: "Accès enregistré",
    whos_driving: "Qui conduit",
    mode_household: "Foyer",
    mode_service: "Service",
    mode_guest: "Invité",
    nobody: "Personne",
    automations_suppressed: "Ford Assistant retient certaines actions pour ce mode.",
    reverts_at: "Retour au mode Foyer à {time}",
    action_blocked: "Cette action est bloquée tant que ce mode est actif.",
    alarm_going: "Alarme !",
    locking: "Verrouillage…",
    unlocking: "Déverrouillage…",
    lock_jammed: "Serrure bloquée",
    running: "En marche",
    driving: "En route",
    door_open: "Porte ouverte",
    unlocked: "Déverrouillé",
    locked: "Verrouillé",
    parked: "Garé",
    unknown: "Inconnu",
    home: "Maison",
    away: "Absent",
    lock: "Verrouiller",
    unlock: "Déverrouiller",
    start: "Démarrer",
    stop: "Arrêter",
    extend: "Prolonger",
    honk: "Klaxon et feux",
    garage_open: "Ouvrir le garage",
    garage_close: "Fermer le garage",
    refresh: "Actualiser",
    sending: "Envoi…",
    failed: "Impossible de {action} : {error}",
    fuel: "Carburant",
    battery: "Batterie",
    range: "Autonomie {range} {unit}",
    charging: "Recharge",
    remote_start: "Démarrage à distance",
    min_left: "{minutes} min restantes",
    doors: "Portes",
    n_open: "{count} ouverte(s)",
    all_closed: "Toutes fermées",
    windows: "Fenêtres",
    location: "Position",
    tire_pressure: "Pression des pneus",
    oil_life: "Durée de vie de l'huile",
    battery_12v: "Batterie 12 V",
    alarm: "Alarme",
    warning_lights: "Voyants",
    n_on: "{count} allumé(s)",
    none: "Aucun",
    outside: "Extérieur",
    odometer: "Compteur kilométrique",
    security: "Sécurité",
    alerts: "Alertes",
    garage: "Garage",
    notifications: "Notifications",
    thresholds: "Seuils et horaires",
    cancel: "Annuler",
    confirm_unlock_title: "Déverrouiller {name} ?",
    confirm_unlock_text: "Toutes les portes seront déverrouillées.",
    confirm_start_title: "Démarrer {name} ?",
    confirm_start_text: "Le moteur démarrera à distance et tournera jusqu'à la fin de la minuterie ou jusqu'à ce que vous l'arrêtiez.",
    confirm_garage_title: "Ouvrir le garage ?",
    confirm_garage_text: "La porte du garage va s'ouvrir.",
    open: "Ouvrir",
    value_Open: "Ouvertes",
    value_Closed: "Fermées",
    value_ARMED: "Activée",
    value_PREARMED: "Activation",
    value_DISARMED: "Désactivée",
    value_TRIGGERED: "Déclenchée",
    value_CONNECTED: "Branché",
    value_DISCONNECTED: "Débranché",
    value_STOPPED: "Arrêtée",
    value_COMPLETED: "Terminée",
    value_FAULT: "Défaut",
    value_STATION_NOT_DETECTED: "Borne introuvable",
    door_hood: "Capot",
    door_tailgate: "Hayon",
    door_innerTailgate: "Hayon intérieur",
    door_driverFront: "Avant conducteur",
    door_passengerFront: "Avant passager",
    door_driverRear: "Arrière conducteur",
    door_passengerRear: "Arrière passager",
    tire_FL: "AvG",
    tire_FR: "AvD",
    tire_RL: "ArG",
    tire_RR: "ArD",
  },
};

const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );

const humanize = (value) => {
  const text = String(value ?? "")
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
};

const num = (value) => {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : null;
};

class FordAssistantPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._vehicles = null;
    this._error = null;
    this._selected = null;
    this._pending = new Map(); // action -> {timer, watch, from}
    this._confirm = null;
    this._signature = null;
    this._images = new Map();
    this._built = false;
  }

  // ----------------------------------------------------------- HA properties

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._load();
    this._resolvePending();
    // Home Assistant sends a new hass on every state change in the house:
    // look further only when one of this vehicle's own entities changed, and
    // not at all while nobody can see the page (it catches up when seen).
    if (!this._ownChanged() && !first) return;
    this._render();
  }

  // Whether a state the page shows has a new state object since the last look.
  _ownChanged() {
    if (pageHidden()) {
      this._staleView = true;
      this._whenVisible();
      return false;
    }
    const vehicle = this._vehicle;
    if (vehicle !== this._ownVehicle) {
      this._ownVehicle = vehicle;
      this._ownIds = vehicle ? this._signatureIds(vehicle) : [];
      this._ownStates = null;
    }
    const states = this._ownIds.map((id) => this._state(id));
    const before = this._ownStates;
    this._ownStates = states;
    const changed = this._staleView || !before || states.some((s, i) => s !== before[i]);
    this._staleView = false;
    return changed;
  }

  // Draw once when a hidden page is seen again.
  _whenVisible() {
    if (this._onVisible) return;
    this._onVisible = () => {
      if (pageHidden() || !this._staleView) return;
      this._staleView = false;
      this._ownStates = null;
      this._render();
    };
    document.addEventListener("visibilitychange", this._onVisible);
  }

  get hass() {
    return this._hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._render(true);
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    this._build();
    this._render(true);
  }

  disconnectedCallback() {
    for (const pending of this._pending.values()) clearTimeout(pending.timer);
    this._pending.clear();
    if (this._onVisible) {
      document.removeEventListener("visibilitychange", this._onVisible);
      this._onVisible = null;
    }
  }

  // ----------------------------------------------------------------- data

  async _load() {
    this._error = null;
    try {
      const result = await this._hass.callWS({ type: "ford_assistant/vehicles" });
      this._vehicles = result.vehicles || [];
      let saved = null;
      try {
        saved = window.localStorage.getItem(STORAGE_KEY);
      } catch (_err) {
        saved = null;
      }
      const match = this._vehicles.find((v) => v.entry_id === saved);
      this._selected = (match || this._vehicles[0] || {}).entry_id || null;
    } catch (err) {
      if (err && err.code === "unauthorized") this._denied = true;
      else this._error = (err && err.message) || String(err);
    }
    this._render(true);
  }

  // Admins choose who else may use the dashboard.
  async _loadAccess() {
    if (this._accessLoading || !this._hass?.user?.is_admin) return;
    this._accessLoading = true;
    try {
      const res = await this._hass.callWS({ type: "ford_assistant/access/get" });
      this._access = { people: res?.people || [], ids: new Set(res?.user_ids || []) };
    } catch (err) {
      this._access = { people: [], ids: new Set(), error: (err && err.message) || String(err) };
    }
    this._accessLoading = false;
    this._render(true);
  }

  async _saveAccess() {
    const ids = [...this.shadowRoot.querySelectorAll("[data-access-user]")]
      .filter((box) => box.checked)
      .map((box) => box.dataset.accessUser);
    try {
      const res = await this._hass.callWS({ type: "ford_assistant/access/set", user_ids: ids });
      this._access = { people: res?.people || [], ids: new Set(res?.user_ids || []), saved: true };
    } catch (err) {
      this._access = { ...this._access, error: (err && err.message) || String(err) };
    }
    this._render(true);
  }

  _accessView() {
    if (!this._hass?.user?.is_admin) return "";
    const a = this._access;
    if (!a) {
      this._loadAccess();
      return "";
    }
    const others = a.people.filter((p) => !p.is_admin);
    const rows = others.length
      ? others
          .map(
            (p) => `<label class="access-person"><input type="checkbox" data-action="access"
              data-access-user="${esc(p.id)}" ${a.ids.has(p.id) ? "checked" : ""}> ${esc(p.name)}</label>`,
          )
          .join("")
      : `<p class="muted">${esc(this._t("access_all_admins"))}</p>`;
    const anyone = others.some((p) => a.ids.has(p.id));
    return `<section class="card access">
      <h2>${esc(this._t("access_title"))}</h2>
      <p class="muted">${esc(this._t("access_text"))}</p>
      <div class="access-people">${rows}</div>
      ${anyone ? `<p class="muted">${esc(this._t("access_sidebar"))}</p>` : ""}
      ${a.error ? `<p class="muted" role="alert">${esc(a.error)}</p>` : a.saved ? `<p class="muted" role="status">${esc(this._t("access_saved"))}</p>` : ""}
    </section>`;
  }

  _deniedView() {
    return `<div class="message card">
      <ha-icon icon="mdi:lock-outline"></ha-icon>
      <h2>${esc(this._t("denied_title"))}</h2>
      <p>${esc(this._t("denied_text"))}</p>
    </div>`;
  }

  get _vehicle() {
    return (this._vehicles || []).find((v) => v.entry_id === this._selected) || null;
  }

  // Text in the viewer's language (English when it isn't translated).
  _t(key, values = {}) {
    const code = String(this._hass?.locale?.language || this._hass?.language || "en");
    const words = WORDS[code.split(/[-_]/)[0].toLowerCase()] || WORDS.en;
    const text = words[key] ?? WORDS.en[key] ?? key;
    return text.replace(/\{(\w+)\}/g, (match, name) => (name in values ? String(values[name]) : match));
  }

  // A reading from the Ford integration, in words when we know it.
  _word(prefix, value) {
    const key = `${prefix}_${value}`;
    return key in WORDS.en ? this._t(key) : humanize(value);
  }

  _state(entityId) {
    return entityId && this._hass ? this._hass.states[entityId] : undefined;
  }

  _value(entityId) {
    const state = this._state(entityId);
    return state ? state.state : undefined;
  }

  _format(entityId) {
    const state = this._state(entityId);
    if (!state || BAD.has(state.state)) return "—";
    if (this._hass.formatEntityState) return this._hass.formatEntityState(state);
    const unit = state.attributes.unit_of_measurement;
    return unit ? `${state.state} ${unit}` : state.state;
  }

  _signatureIds(vehicle) {
    return [
      ...Object.values(vehicle.ford),
      ...Object.values(vehicle.assistant.switch),
      ...Object.values(vehicle.assistant.number),
      ...Object.values(vehicle.assistant.sensor),
      ...Object.values(vehicle.assistant.select || {}),
      ...Object.values(vehicle.assistant.time || {}),
      ...Object.values(vehicle.assistant.binary_sensor || {}),
      vehicle.garage,
      vehicle.home_zone,
    ];
  }

  _signatureFor(vehicle) {
    if (!vehicle) return "";
    return this._signatureIds(vehicle)
      .map((id) => {
        const s = this._state(id);
        return s ? `${id}=${s.state}@${s.last_updated}` : `${id}=`;
      })
      .join("|");
  }

  // -------------------------------------------------------------- render

  _build() {
    if (this._built) return;
    this._built = true;
    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <div class="toolbar">
        <div class="menu"></div>
        <div class="title">Ford Assistant</div>
      </div>
      <div class="tabs" role="tablist"></div>
      <main class="content"></main>
      <div class="dialog-root"></div>
    `;
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && this._confirm) {
        this._confirm = null;
        this._render(true);
      }
    });
  }

  _render(force = false) {
    if (!this._built || !this._hass) return;

    const menu = this.shadowRoot.querySelector(".menu");
    let button = menu.querySelector("ha-menu-button");
    if (!button) {
      button = document.createElement("ha-menu-button");
      menu.appendChild(button);
    }
    button.hass = this._hass;
    button.narrow = this._narrow;

    const signature = [
      this._vehicles ? this._vehicles.length : "loading",
      this._error,
      this._selected,
      this._narrow,
      [...this._pending.keys()].join(","),
      this._confirm ? this._confirm.action : "",
      this._signatureFor(this._vehicle),
    ].join("#");
    if (!force && signature === this._signature) return;
    this._signature = signature;

    this._renderTabs();
    const content = this.shadowRoot.querySelector(".content");
    if (this._denied) {
      content.innerHTML = this._deniedView();
    } else if (this._error) {
      content.innerHTML = this._errorView();
    } else if (!this._vehicles) {
      content.innerHTML = this._skeletonView();
    } else if (!this._vehicles.length) {
      content.innerHTML = this._emptyView();
    } else {
      content.innerHTML = this._vehicleView(this._vehicle);
      this._placeImage(this._vehicle);
    }
    this.shadowRoot.querySelector(".dialog-root").innerHTML = this._confirmView();
    const confirmButton = this.shadowRoot.querySelector(".dialog [data-confirm]");
    if (confirmButton) confirmButton.focus();
  }

  _renderTabs() {
    const tabs = this.shadowRoot.querySelector(".tabs");
    const vehicles = this._vehicles || [];
    tabs.hidden = vehicles.length < 2;
    tabs.innerHTML = vehicles
      .map(
        (v) => `<button class="tab ${v.entry_id === this._selected ? "active" : ""}"
          role="tab" aria-selected="${v.entry_id === this._selected}"
          data-action="select" data-entry="${esc(v.entry_id)}">${esc(v.name)}</button>`,
      )
      .join("");
  }

  _skeletonView() {
    const tile = `<div class="tile skeleton-tile"><div class="sk sk-line short"></div>
      <div class="sk sk-line big"></div><div class="sk sk-line"></div></div>`;
    return `
      <div class="loading" aria-busy="true" aria-label="${esc(this._t("loading"))}">
        <section class="hero"><div class="image-wrap"><div class="sk sk-image"></div></div>
          <div class="hero-text"><div class="sk sk-line title"></div><div class="sk sk-line short"></div></div>
        </section>
        <section class="actions">${'<div class="sk sk-action"></div>'.repeat(4)}</section>
        <section class="grid">${tile.repeat(6)}</section>
      </div>`;
  }

  _errorView() {
    return `<div class="message card">
      <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
      <h2>${esc(this._t("load_failed"))}</h2>
      <p>${esc(this._error)}</p>
      <button class="button primary" data-action="retry">${esc(this._t("try_again"))}</button>
    </div>`;
  }

  _emptyView() {
    return `<div class="message card">
      <ha-icon icon="mdi:car-off"></ha-icon>
      <h2>${esc(this._t("no_vehicles"))}</h2>
      <p>${esc(this._t("no_vehicles_text"))}</p>
      <button class="button primary" data-action="navigate"
        data-path="/config/integrations/integration/ford_assistant">${esc(this._t("open_integration"))}</button>
    </div>`;
  }

  // ------------------------------------------------------------- vehicle

  _status(v) {
    const f = v.ford;
    const alarm = this._value(f.alarm);
    const alarmGoing = !BAD.has(alarm) && !["ARMED", "PREARMED", "DISARMED"].includes(alarm);
    const running = this._value(f.remote_start) === "on";
    const ignition = this._value(f.ignition);
    const driving = !running && !BAD.has(ignition) && String(ignition).toUpperCase() !== "OFF";
    const doorsOpen = this._value(f.doors) === "Open";
    const lock = this._value(f.lock);
    const home = this._atHome(v);
    // Tapped Lock or Unlock and the vehicle hasn't confirmed yet. The Ford
    // integration also reports "locking"/"unlocking" while it sends one.
    const locking = this._pendingFor(v, "lock") || lock === "locking";
    const unlocking = this._pendingFor(v, "unlock") || lock === "unlocking";
    if (alarmGoing) return { text: this._t("alarm_going"), tone: "error", icon: "mdi:alarm-light" };
    if (locking) return { text: this._t("locking"), tone: "info", icon: "mdi:lock-clock" };
    if (unlocking) return { text: this._t("unlocking"), tone: "info", icon: "mdi:lock-clock" };
    if (lock === "jammed") return { text: this._t("lock_jammed"), tone: "error", icon: "mdi:lock-alert" };
    if (running) return { text: this._t("running"), tone: "info", icon: "mdi:engine" };
    if (driving) return { text: this._t("driving"), tone: "info", icon: "mdi:steering" };
    if (doorsOpen) return { text: this._t("door_open"), tone: "error", icon: "mdi:car-door" };
    if (lock === "unlocked")
      return { text: this._t("unlocked"), tone: home ? "warning" : "error", icon: "mdi:lock-open-variant" };
    if (lock === "locked") return { text: this._t("locked"), tone: "success", icon: "mdi:lock" };
    return { text: this._t("parked"), tone: "neutral", icon: "mdi:car" };
  }

  _atHome(v) {
    const tracker = this._state(v.ford.tracker);
    if (!tracker) return false;
    const zones = tracker.attributes.in_zones;
    if (Array.isArray(zones)) return zones.includes(v.home_zone);
    return tracker.state === "home";
  }

  _place(v) {
    const tracker = this._state(v.ford.tracker);
    if (!tracker || BAD.has(tracker.state)) return this._t("unknown");
    if (this._atHome(v)) return this._t("home");
    if (tracker.state === "not_home") return this._t("away");
    const zone = this._hass.states[`zone.${tracker.state}`];
    return zone ? zone.attributes.friendly_name || tracker.state : humanize(tracker.state);
  }

  _vehicleView(v) {
    const status = this._status(v);
    const subtitle = [v.manufacturer, v.model].filter(Boolean).join(" ");
    const lastEvent = this._state(v.assistant.sensor.last_event);
    return `
      <section class="hero card">
        <div class="image-wrap" data-slot="image"></div>
        <div class="hero-text">
          <h1>${esc(v.name)}</h1>
          ${subtitle ? `<div class="subtitle">${esc(subtitle)}</div>` : ""}
          <span class="chip ${status.tone}"><ha-icon icon="${status.icon}"></ha-icon>${esc(status.text)}</span>
          ${
            lastEvent && !BAD.has(lastEvent.state)
              ? `<button class="last-event" data-action="more-info" data-entity="${esc(lastEvent.entity_id)}">
                  <ha-icon icon="mdi:history"></ha-icon><span>${esc(lastEvent.state)}</span></button>`
              : ""
          }
        </div>
      </section>
      ${this._drivingCard(v)}
      <section class="actions">${this._actions(v)}</section>
      <section class="grid">${this._tiles(v)}</section>
      ${this._featuresView(v)}
      ${this._accessView()}
    `;
  }

  _placeImage(v) {
    const slot = this.shadowRoot.querySelector('[data-slot="image"]');
    if (!slot) return;
    const image = this._state(v.ford.image);
    const url = image && image.attributes.entity_picture;
    if (!url) {
      slot.innerHTML = `<div class="image-fallback"><ha-icon icon="mdi:car-side"></ha-icon></div>`;
      return;
    }
    // Keep one <img> per vehicle so re-renders don't reload or flicker it.
    let entry = this._images.get(v.entry_id);
    if (!entry || entry.url !== url) {
      const img = document.createElement("img");
      img.alt = v.name;
      img.decoding = "async";
      entry = { url, img, loaded: false, failed: false };
      img.addEventListener("load", () => {
        entry.loaded = true;
        img.classList.add("loaded");
        const sk = img.parentElement && img.parentElement.querySelector(".sk-image");
        if (sk) sk.remove();
      });
      img.addEventListener("error", () => {
        entry.failed = true;
        this._render(true);
      });
      img.src = url;
      this._images.set(v.entry_id, entry);
    }
    if (entry.failed) {
      slot.innerHTML = `<div class="image-fallback"><ha-icon icon="mdi:car-side"></ha-icon></div>`;
      return;
    }
    slot.innerHTML = entry.loaded ? "" : `<div class="sk sk-image"></div>`;
    slot.appendChild(entry.img);
  }

  _policy(v) {
    const id = v.assistant.select && v.assistant.select.driving_mode;
    const state = id && this._state(id);
    if (!state || BAD.has(state.state)) {
      return { mode: "household", blocked: [], driver: "", revert: "", suppressed: false };
    }
    const attrs = state.attributes || {};
    return {
      mode: state.state,
      blocked: attrs.blocked_actions || [],
      driver: attrs.active_driver_name || "",
      revert: attrs.revert_at || "",
      suppressed: !!attrs.automations_suppressed,
    };
  }

  _blocked(v, action) {
    const key = ACTION_BLOCKS[action];
    return !!key && this._policy(v).blocked.includes(key);
  }

  _drivingCard(v) {
    const policy = this._policy(v);
    const mode = this._t("mode_" + (policy.mode || "household"));
    const bits = [mode];
    if ((policy.mode || "household") === "household") {
      bits.push(policy.driver || this._t("nobody"));
    }
    let when = "";
    if (policy.revert) {
      const parsed = new Date(policy.revert);
      when = Number.isNaN(parsed.getTime())
        ? policy.revert
        : parsed.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
    }
    const entity = v.assistant.select && v.assistant.select.driving_mode;
    return `<section class="card driving">
      <h2>${esc(this._t("whos_driving"))}</h2>
      <p class="driving-mode">${esc(bits.join(" · "))}</p>
      ${policy.suppressed ? `<p class="muted">${esc(this._t("automations_suppressed"))}</p>` : ""}
      ${when ? `<p class="muted">${esc(this._t("reverts_at", { time: when }))}</p>` : ""}
      ${
        entity
          ? `<button class="last-event" data-action="more-info" data-entity="${esc(entity)}">
              <ha-icon icon="mdi:account-switch"></ha-icon><span>${esc(this._t("whos_driving"))}</span></button>`
          : ""
      }
    </section>`;
  }

  _actions(v) {
    const f = v.ford;
    const items = [];
    const held = this._t("action_blocked");
    const lock = this._value(f.lock);
    if (f.lock) {
      // While the vehicle is locking or unlocking, wait for it.
      const busy = BAD.has(lock) || lock === "locking" || lock === "unlocking";
      items.push(
        lock === "locking"
          ? this._action("lock", "mdi:lock-clock", this._t("locking"), true)
          : lock === "unlocking"
            ? this._action("unlock", "mdi:lock-clock", this._t("unlocking"), true)
            : lock === "locked"
              ? this._action("unlock", "mdi:lock-open-variant", this._t("unlock"), busy || this._blocked(v, "unlock"), "", this._blocked(v, "unlock") ? held : "")
              : this._action("lock", "mdi:lock", this._t("lock"), busy || this._blocked(v, "lock"), "", this._blocked(v, "lock") ? held : ""),
      );
    }
    if (f.remote_start) {
      const running = this._value(f.remote_start) === "on";
      items.push(
        running
          ? this._action("stop", "mdi:engine-off", this._t("stop"), this._blocked(v, "stop"), "active", this._blocked(v, "stop") ? held : "")
          : this._action("start", "mdi:engine", this._t("start"), BAD.has(this._value(f.remote_start)) || this._blocked(v, "start"), "", this._blocked(v, "start") ? held : ""),
      );
      // Button entities stay "unknown" until first pressed, so only hide unavailable ones.
      if (running && f.extend && this._usable(f.extend)) {
        items.push(this._action("extend", "mdi:timer-plus", this._t("extend"), this._blocked(v, "extend"), "", this._blocked(v, "extend") ? held : ""));
      }
    }
    if (f.honk && this._usable(f.honk)) {
      items.push(this._action("honk", "mdi:car-light-high", this._t("honk"), this._blocked(v, "honk"), "", this._blocked(v, "honk") ? held : ""));
    }
    if (v.garage && this._state(v.garage)) {
      const garage = this._value(v.garage);
      items.push(
        garage === "open" || garage === "opening"
          ? this._action("garage_close", "mdi:garage", this._t("garage_close"), this._blocked(v, "garage_close"), "", this._blocked(v, "garage_close") ? held : "")
          : this._action("garage_open", "mdi:garage-open", this._t("garage_open"), this._blocked(v, "garage_open"), "", this._blocked(v, "garage_open") ? held : ""),
      );
    }
    if (f.refresh && this._usable(f.refresh)) {
      items.push(this._action("refresh", "mdi:refresh", this._t("refresh")));
    }
    return items.join("");
  }

  _pendingFor(v, action) {
    const pending = this._pending.get(action);
    return !!pending && pending.watch === v.ford[action === "unlock" ? "lock" : action];
  }

  _usable(entityId) {
    const state = this._state(entityId);
    return !!state && state.state !== "unavailable";
  }

  _action(action, icon, label, disabled = false, extra = "", title = "") {
    const pending = this._pending.has(action);
    return `<button class="action ${extra} ${pending ? "pending" : ""}" data-action="${action}"
        ${disabled || pending ? "disabled" : ""} aria-label="${esc(label)}"${title ? ` title="${esc(title)}"` : ""}>
      <span class="action-icon">${
        pending ? `<span class="spinner" aria-hidden="true"></span>` : `<ha-icon icon="${icon}"></ha-icon>`
      }</span>
      <span class="action-label">${esc(pending ? this._t(PENDING_LABELS[action] || "sending") : label)}</span>
    </button>`;
  }

  _tiles(v) {
    const f = v.ford;
    const tiles = [];

    // Energy: fuel, or the high-voltage battery on an EV.
    const energyId = f.fuel && !BAD.has(this._value(f.fuel)) ? f.fuel : f.soc;
    const energy = this._state(energyId);
    if (energy) {
      const level = num(energy.state);
      const isFuel = energyId === f.fuel;
      const range = num(energy.attributes[isFuel ? "fuelRange" : "batteryRange"]);
      const threshold = num(this._value(v.assistant.number.fuel_threshold));
      const low = level !== null && threshold !== null && level < threshold;
      const unit = this._hass.config.unit_system ? this._hass.config.unit_system.length : "";
      tiles.push(
        this._tile({
          entity: energyId,
          icon: isFuel ? "mdi:gas-station" : "mdi:battery-charging-high",
          label: this._t(isFuel ? "fuel" : "battery"),
          value: level === null ? "—" : `${Math.round(level)}%`,
          detail: range === null ? "" : this._t("range", { range: Math.round(range), unit }),
          bar: level,
          tone: low ? "error" : "",
          wide: true,
        }),
      );
    }

    if (v.electric && (f.ev_plug || f.ev_charging)) {
      const charging = this._value(f.ev_charging);
      const plug = this._value(f.ev_plug);
      const value =
        charging === "IN_PROGRESS" ? this._t("charging") : !BAD.has(plug) ? this._word("value", plug) : "—";
      tiles.push(
        this._tile({
          entity: f.ev_charging || f.ev_plug,
          icon: charging === "IN_PROGRESS" ? "mdi:ev-station" : "mdi:ev-plug-type1",
          label: this._t("charging"),
          value,
          detail: !BAD.has(charging) && charging !== "IN_PROGRESS" ? this._word("value", charging) : "",
          tone: ["FAULT", "STATION_NOT_DETECTED"].includes(charging) ? "error" : "",
        }),
      );
    }

    if (f.remote_start && this._value(f.remote_start) === "on") {
      const minutes = num(this._value(f.countdown));
      tiles.push(
        this._tile({
          entity: f.countdown || f.remote_start,
          icon: "mdi:timer-sand",
          label: this._t("remote_start"),
          value: minutes ? this._t("min_left", { minutes: Math.round(minutes) }) : this._t("running"),
          tone: "info",
        }),
      );
    }

    if (f.doors) {
      const doors = this._state(f.doors);
      const open = doors
        ? Object.entries(doors.attributes)
            .filter(
              ([, val]) =>
                typeof val === "string" && /^[A-Z_]+$/.test(val) &&
                !["CLOSED", "INVALID", "UNKNOWN", "UNSUPPORTED"].includes(val),
            )
            .map(([key]) => this._word("door", key))
        : [];
      tiles.push(
        this._tile({
          entity: f.doors,
          icon: open.length ? "mdi:car-door" : "mdi:car-door-lock",
          label: this._t("doors"),
          value: open.length ? this._t("n_open", { count: open.length }) : doors ? this._t("all_closed") : "—",
          detail: open.join(", "),
          tone: open.length ? "error" : "",
        }),
      );
    }

    if (f.windows) {
      const windows = this._value(f.windows);
      tiles.push(
        this._tile({
          entity: f.windows,
          icon: windows === "Open" ? "mdi:car-door" : "mdi:window-closed-variant",
          label: this._t("windows"),
          value: BAD.has(windows) ? "—" : this._word("value", windows),
          tone: windows === "Open" && !this._atHome(v) ? "warning" : "",
        }),
      );
    }

    if (f.tracker) {
      tiles.push(
        this._tile({
          entity: f.tracker,
          icon: this._atHome(v) ? "mdi:home" : "mdi:map-marker",
          label: this._t("location"),
          value: this._place(v),
        }),
      );
    }

    if (f.tires) tiles.push(this._tiresTile(f.tires));

    if (f.oil) {
      const oil = num(this._value(f.oil));
      const threshold = num(this._value(v.assistant.number.oil_threshold));
      tiles.push(
        this._tile({
          entity: f.oil,
          icon: "mdi:oil",
          label: this._t("oil_life"),
          value: oil === null ? "—" : `${Math.round(oil)}%`,
          bar: oil,
          tone: oil !== null && threshold !== null && oil < threshold ? "warning" : "",
        }),
      );
    }

    if (f.battery) {
      const battery = this._state(f.battery);
      const level = num(battery && battery.state);
      const volts = battery ? num(battery.attributes.batteryVoltage) : null;
      const threshold = num(this._value(v.assistant.number.battery_threshold));
      tiles.push(
        this._tile({
          entity: f.battery,
          icon: "mdi:car-battery",
          label: this._t("battery_12v"),
          value: level === null ? "—" : `${Math.round(level)}%`,
          detail: volts === null ? "" : `${volts.toFixed(1)} V`,
          tone: level !== null && threshold !== null && level < threshold ? "warning" : "",
        }),
      );
    }

    if (f.alarm) {
      const alarm = this._value(f.alarm);
      const going = !BAD.has(alarm) && !["ARMED", "PREARMED", "DISARMED"].includes(alarm);
      tiles.push(
        this._tile({
          entity: f.alarm,
          icon: going ? "mdi:alarm-light" : "mdi:shield-car",
          label: this._t("alarm"),
          value: BAD.has(alarm) ? "—" : this._word("value", alarm),
          tone: going ? "error" : "",
        }),
      );
    }

    if (f.indicators) {
      const indicators = this._state(f.indicators);
      const on = indicators
        ? Object.entries(indicators.attributes)
            .filter(([, val]) => val === true)
            .map(([key]) => humanize(key.replace(/_[0-9A-Za-z]+$/, "")))
        : [];
      tiles.push(
        this._tile({
          entity: f.indicators,
          icon: on.length ? "mdi:car-light-alert" : "mdi:car-info",
          label: this._t("warning_lights"),
          value: on.length ? this._t("n_on", { count: on.length }) : indicators ? this._t("none") : "—",
          detail: on.join(", "),
          tone: on.length ? "warning" : "",
        }),
      );
    }

    if (f.temperature) {
      tiles.push(
        this._tile({
          entity: f.temperature,
          icon: "mdi:thermometer",
          label: this._t("outside"),
          value: this._format(f.temperature),
        }),
      );
    }

    if (f.odometer) {
      tiles.push(
        this._tile({
          entity: f.odometer,
          icon: "mdi:counter",
          label: this._t("odometer"),
          value: this._format(f.odometer),
        }),
      );
    }

    return tiles.join("");
  }

  _tile({ entity, icon, label, value, detail = "", bar = null, tone = "", wide = false }) {
    const barHtml =
      bar === null || bar === undefined
        ? ""
        : `<div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100"
            aria-valuenow="${Math.round(bar)}"><div style="width:${Math.max(0, Math.min(100, bar))}%"></div></div>`;
    return `<button class="tile ${tone} ${wide ? "wide" : ""}" data-action="more-info"
        data-entity="${esc(entity)}">
      <div class="tile-head"><ha-icon icon="${icon}"></ha-icon><span>${esc(label)}</span></div>
      <div class="tile-value">${esc(value)}</div>
      ${detail ? `<div class="tile-detail">${esc(detail)}</div>` : ""}
      ${barHtml}
    </button>`;
  }

  _tiresTile(entityId) {
    const tires = this._state(entityId);
    const attrs = tires ? tires.attributes : {};
    const system = tires ? tires.state : undefined;
    const warn = !BAD.has(system) && system !== "NORMAL_OPERATION";
    const wheels = TIRES.map(([key, short]) => {
      const state = attrs[`${key}_state`];
      const bad = state && state !== "NORMAL";
      return `<div class="wheel ${bad ? "bad" : ""}"><span>${esc(this._t(`tire_${short}`))}</span>
        <strong>${esc(attrs[key] !== undefined ? attrs[key] : "—")}</strong></div>`;
    }).join("");
    return `<button class="tile tires ${warn ? "warning" : ""}" data-action="more-info"
        data-entity="${esc(entityId)}">
      <div class="tile-head"><ha-icon icon="mdi:car-tire-alert"></ha-icon><span>${esc(this._t("tire_pressure"))}</span></div>
      <div class="wheels">${wheels}</div>
      ${warn ? `<div class="tile-detail">${esc(humanize(system))}</div>` : ""}
    </button>`;
  }

  _featuresView(v) {
    const switches = v.assistant.switch;
    const groups = FEATURE_GROUPS.map((group) => {
      const rows = group.keys
        .filter((key) => switches[key] && this._state(switches[key]))
        .map((key) => {
          const entityId = switches[key];
          const state = this._state(entityId);
          const on = state.state === "on";
          let label = state.attributes.friendly_name || humanize(key);
          if (label.startsWith(`${v.name} `)) label = label.slice(v.name.length + 1);
          label = label.charAt(0).toUpperCase() + label.slice(1);
          return `<div class="feature">
            <button class="feature-name" data-action="more-info" data-entity="${esc(entityId)}">${esc(label)}</button>
            <button class="toggle ${on ? "on" : ""}" role="switch" aria-checked="${on}"
              aria-label="${esc(label)}" data-action="toggle" data-entity="${esc(entityId)}"
              ${BAD.has(state.state) ? "disabled" : ""}><span></span></button>
          </div>`;
        })
        .join("");
      return rows ? `<div class="group"><h3>${esc(this._t(group.title))}</h3>${rows}</div>` : "";
    }).join("");
    if (!groups) return "";
    const settings = v.assistant_device_id
      ? `<button class="button" data-action="navigate"
          data-path="/config/devices/device/${esc(v.assistant_device_id)}">
          <ha-icon icon="mdi:tune-variant"></ha-icon>${esc(this._t("thresholds"))}</button>`
      : "";
    return `<section class="card features">
      <div class="features-head"><h2>Ford Assistant</h2>${settings}</div>
      <div class="groups">${groups}</div>
    </section>`;
  }

  _confirmView() {
    if (!this._confirm) return "";
    const { title, text, label } = this._confirm;
    return `<div class="scrim" data-action="cancel"></div>
      <div class="dialog card" role="alertdialog" aria-modal="true" aria-labelledby="fa-dialog-title">
        <h2 id="fa-dialog-title">${esc(title)}</h2>
        <p>${esc(text)}</p>
        <div class="dialog-buttons">
          <button class="button" data-action="cancel">${esc(this._t("cancel"))}</button>
          <button class="button primary" data-confirm data-action="confirm">${esc(label)}</button>
        </div>
      </div>`;
  }

  // ------------------------------------------------------------- actions

  _onClick(ev) {
    const target = ev.composedPath().find((el) => el.dataset && el.dataset.action);
    if (!target || target.disabled) return;
    const { action, entity, entry, path } = target.dataset;
    const v = this._vehicle;
    switch (action) {
      case "select":
        this._selected = entry;
        try {
          window.localStorage.setItem(STORAGE_KEY, entry);
        } catch (_err) {
          /* private mode */
        }
        this._render(true);
        return;
      case "retry":
        this._vehicles = null;
        this._error = null;
        this._render(true);
        this._load();
        return;
      case "more-info":
        this.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: { entityId: entity },
            bubbles: true,
            composed: true,
          }),
        );
        return;
      case "navigate":
        window.history.pushState(null, "", path);
        window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
        return;
      case "access":
        // Let the checkbox change first, then save who's checked.
        setTimeout(() => this._saveAccess(), 0);
        return;
      case "toggle":
        this._hass.callService("switch", "toggle", { entity_id: entity });
        return;
      case "cancel":
        this._confirm = null;
        this._render(true);
        return;
      case "confirm": {
        const pending = this._confirm;
        this._confirm = null;
        if (pending) this._run(pending.action, v);
        return;
      }
      default:
        if (v) this._command(action, v);
    }
  }

  _command(action, v) {
    if (this._blocked(v, action)) {
      this._toast(this._t("action_blocked"));
      return;
    }
    const confirms = {
      unlock: {
        title: this._t("confirm_unlock_title", { name: v.name }),
        text: this._t("confirm_unlock_text"),
        label: this._t("unlock"),
      },
      start: {
        title: this._t("confirm_start_title", { name: v.name }),
        text: this._t("confirm_start_text"),
        label: this._t("start"),
      },
      garage_open: {
        title: this._t("confirm_garage_title"),
        text: this._t("confirm_garage_text"),
        label: this._t("open"),
      },
    };
    if (confirms[action]) {
      this._confirm = { action, ...confirms[action] };
      this._render(true);
      return;
    }
    this._run(action, v);
  }

  _run(action, v) {
    if (this._blocked(v, action)) {
      this._toast(this._t("action_blocked"));
      return;
    }
    const f = v.ford;
    const calls = {
      lock: ["lock", "lock", f.lock, f.lock],
      unlock: ["lock", "unlock", f.lock, f.lock],
      start: ["switch", "turn_on", f.remote_start, f.remote_start],
      stop: ["switch", "turn_off", f.remote_start, f.remote_start],
      extend: ["button", "press", f.extend, f.countdown],
      honk: ["button", "press", f.honk, f.honk],
      refresh: ["button", "press", f.refresh, f.refresh],
      garage_open: ["cover", "open_cover", v.garage, v.garage],
      garage_close: ["cover", "close_cover", v.garage, v.garage],
    };
    const call = calls[action];
    if (!call || !call[2]) return;
    const [domain, service, entityId, watch] = call;
    const from = this._state(watch) ? this._state(watch).last_updated : null;
    const timer = setTimeout(() => {
      this._pending.delete(action);
      this._render(true);
    }, LOCK_DONE[action] ? LOCK_TIMEOUT : PENDING_TIMEOUT);
    this._pending.set(action, { timer, watch, from, until: LOCK_DONE[action] });
    this._render(true);
    Promise.resolve(this._hass.callService(domain, service, { entity_id: entityId })).catch((err) => {
      clearTimeout(timer);
      this._pending.delete(action);
      const what = this._t(action === "honk" ? "honk" : action).toLowerCase();
      this._toast(this._t("failed", { action: what, error: (err && err.message) || err }));
      this._render(true);
    });
  }

  _resolvePending() {
    // A command is done once the entity it affects reports a new state.
    // Lock and unlock wait for the lock to say locked or unlocked: on the
    // way it reports "locking", and then briefly its old state until the
    // vehicle answers.
    for (const [action, pending] of this._pending) {
      const state = this._state(pending.watch);
      const done = pending.until ? state && state.state === pending.until : state && state.last_updated !== pending.from;
      if (done) {
        clearTimeout(pending.timer);
        this._pending.delete(action);
      }
    }
  }

  _toast(message) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }),
    );
  }
}

const STYLES = `
  :host {
    display: block;
    min-height: 100%;
    background: var(--primary-background-color, #fafafa);
    color: var(--primary-text-color, #212121);
    font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, sans-serif));
    --fa-radius: var(--ha-card-border-radius, 12px);
    --fa-card: var(--card-background-color, var(--ha-card-background, #fff));
    --fa-muted: var(--secondary-text-color, #727272);
    --fa-divider: var(--divider-color, rgba(0, 0, 0, 0.12));
    --fa-primary: var(--primary-color, #03a9f4);
    --fa-success: var(--success-color, #43a047);
    --fa-warning: var(--warning-color, #ffa600);
    --fa-error: var(--error-color, #db4437);
    --fa-info: var(--info-color, #039be5);
    --fa-skeleton: var(--secondary-background-color, #e5e5e5);
  }
  * { box-sizing: border-box; }
  button { font: inherit; color: inherit; }
  ha-icon { --mdc-icon-size: 20px; }

  .toolbar {
    display: flex; align-items: center; gap: 4px;
    height: var(--header-height, 56px); padding: 0 12px;
    background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, var(--text-primary-color, #fff));
    position: sticky; top: 0; z-index: 2;
  }
  .title { font-size: 20px; font-weight: 400; margin-left: 4px; }

  .tabs {
    display: flex; gap: 8px; overflow-x: auto; padding: 12px 16px 0;
    max-width: 1100px; margin: 0 auto;
  }
  .tabs[hidden] { display: none; }
  .driving { padding: 16px; }
  .driving h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; }
  .driving p { margin: 0 0 8px; }
  .driving .muted { color: var(--fa-muted); font-size: 14px; }
  .driving .last-event { margin-top: 4px; }
  .access { padding: 16px; }
  .access h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; }
  .access p { margin: 8px 0; font-size: 14px; }
  .access .access-people { display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 12px 0; }
  .access-person { display: inline-flex; align-items: center; gap: 6px; min-height: 44px; }
  .access .muted { color: var(--fa-muted); }
  .tab {
    border: 1px solid var(--fa-divider); background: var(--fa-card);
    border-radius: 999px; padding: 6px 14px; cursor: pointer; white-space: nowrap;
  }
  .tab.active { background: var(--fa-primary); border-color: var(--fa-primary); color: var(--text-primary-color, #fff); }

  .content { max-width: 1100px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }
  .loading { display: flex; flex-direction: column; gap: 16px; }

  .card {
    background: var(--fa-card); border-radius: var(--fa-radius);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--fa-divider));
    box-shadow: var(--ha-card-box-shadow, none);
  }

  /* Hero */
  .hero { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 16px; padding: 16px; align-items: center; }
  .image-wrap {
    position: relative; aspect-ratio: 16 / 9; border-radius: calc(var(--fa-radius) - 4px);
    overflow: hidden; display: flex; align-items: center; justify-content: center;
  }
  .image-wrap img {
    position: relative; width: 100%; height: 100%; object-fit: contain;
    opacity: 0; transform: scale(0.98); transition: opacity 0.45s ease, transform 0.45s ease;
  }
  .image-wrap img.loaded { opacity: 1; transform: none; }
  .image-wrap .sk-image { position: absolute; inset: 0; }
  .image-fallback { color: var(--fa-muted); }
  .image-fallback ha-icon { --mdc-icon-size: 96px; opacity: 0.5; }
  .hero-text { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; min-width: 0; }
  .hero h1 { margin: 0; font-size: 28px; font-weight: 500; line-height: 1.2; overflow-wrap: anywhere; }
  .subtitle { color: var(--fa-muted); }
  .chip {
    display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px;
    font-weight: 500; background: color-mix(in srgb, var(--fa-tone) 16%, transparent); color: var(--fa-tone);
  }
  .chip.success { --fa-tone: var(--fa-success); }
  .chip.warning { --fa-tone: var(--fa-warning); }
  .chip.error { --fa-tone: var(--fa-error); }
  .chip.info { --fa-tone: var(--fa-info); }
  .chip.neutral { --fa-tone: var(--fa-muted); }
  .last-event {
    display: inline-flex; align-items: center; gap: 6px; border: 0; background: none; padding: 0;
    color: var(--fa-muted); cursor: pointer; text-align: left; font-size: 14px;
  }
  .last-event ha-icon { --mdc-icon-size: 16px; flex: none; }

  /* Actions */
  .actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)); gap: 12px; }
  .action {
    display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 14px 8px;
    background: var(--fa-card); border: 1px solid var(--fa-divider); border-radius: var(--fa-radius);
    cursor: pointer; transition: border-color 0.2s, background 0.2s, transform 0.1s;
  }
  .action:hover:not([disabled]) { border-color: var(--fa-primary); }
  .action:active:not([disabled]) { transform: scale(0.97); }
  .action:focus-visible, .tile:focus-visible, .toggle:focus-visible, .tab:focus-visible, .button:focus-visible {
    outline: 2px solid var(--fa-primary); outline-offset: 2px;
  }
  .action[disabled] { opacity: 0.55; cursor: default; }
  .action.pending { opacity: 1; }
  .action.active { border-color: var(--fa-info); background: color-mix(in srgb, var(--fa-info) 10%, var(--fa-card)); }
  .action-icon {
    width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--fa-primary) 14%, transparent); color: var(--fa-primary);
  }
  .action-icon ha-icon { --mdc-icon-size: 24px; }
  .action-label { font-size: 14px; font-weight: 500; text-align: center; }
  .spinner {
    width: 22px; height: 22px; border-radius: 50%;
    border: 3px solid color-mix(in srgb, var(--fa-primary) 25%, transparent); border-top-color: var(--fa-primary);
    animation: fa-spin 0.8s linear infinite;
  }

  /* Tiles */
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; }
  .tile {
    display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 14px;
    text-align: left; cursor: pointer; min-width: 0;
    background: var(--fa-card); border: 1px solid var(--fa-divider); border-radius: var(--fa-radius);
    --fa-tone: var(--fa-primary);
  }
  .tile.wide { grid-column: span 2; }
  .tile.error { --fa-tone: var(--fa-error); border-color: color-mix(in srgb, var(--fa-error) 45%, var(--fa-divider)); }
  .tile.warning { --fa-tone: var(--fa-warning); border-color: color-mix(in srgb, var(--fa-warning) 45%, var(--fa-divider)); }
  .tile.info { --fa-tone: var(--fa-info); }
  .tile-head { display: flex; align-items: center; gap: 6px; color: var(--fa-muted); font-size: 14px; }
  .tile.error .tile-head, .tile.warning .tile-head, .tile.info .tile-head { color: var(--fa-tone); }
  .tile-value { font-size: 24px; font-weight: 500; line-height: 1.25; overflow-wrap: anywhere; }
  .tile-detail { color: var(--fa-muted); font-size: 13px; overflow-wrap: anywhere; }
  .bar { width: 100%; height: 6px; border-radius: 3px; background: var(--fa-skeleton); margin-top: 6px; overflow: hidden; }
  .bar > div { height: 100%; border-radius: 3px; background: var(--fa-tone); transition: width 0.6s ease; }
  .tile.tires { grid-row: span 1; }
  .wheels { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 14px; width: 100%; margin-top: 4px; }
  .wheel { display: flex; justify-content: space-between; gap: 6px; font-size: 14px; }
  .wheel span { color: var(--fa-muted); }
  .wheel.bad strong { color: var(--fa-warning); }

  /* Features */
  .features { padding: 16px; }
  .features-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
  .features h2 { margin: 0; font-size: 20px; font-weight: 500; }
  .groups { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px 24px; }
  .group h3 { margin: 12px 0 4px; font-size: 13px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; color: var(--fa-muted); }
  .feature { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 44px; border-bottom: 1px solid var(--fa-divider); }
  .group .feature:last-child { border-bottom: 0; }
  .feature-name { border: 0; background: none; padding: 0; text-align: left; cursor: pointer; flex: 1; min-width: 0; }
  .toggle {
    flex: none; width: 44px; height: 26px; border-radius: 13px; border: 0; padding: 3px; cursor: pointer;
    background: var(--switch-unchecked-track-color, #9e9e9e); transition: background 0.2s;
  }
  .toggle span { display: block; width: 20px; height: 20px; border-radius: 50%; background: #fff; transition: transform 0.2s; box-shadow: 0 1px 2px rgba(0,0,0,0.3); }
  .toggle.on { background: var(--switch-checked-track-color, var(--fa-primary)); }
  .toggle.on span { transform: translateX(18px); }
  .toggle[disabled] { opacity: 0.5; cursor: default; }

  /* Buttons, messages, dialog */
  .button {
    display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 999px; cursor: pointer;
    border: 1px solid var(--fa-divider); background: transparent; color: var(--fa-primary); font-weight: 500;
  }
  .button.primary { background: var(--fa-primary); border-color: var(--fa-primary); color: var(--text-primary-color, #fff); }
  .message { padding: 32px 24px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 8px; }
  .message ha-icon { --mdc-icon-size: 48px; color: var(--fa-muted); }
  .message h2 { margin: 8px 0 0; font-weight: 500; }
  .message p { margin: 0 0 8px; color: var(--fa-muted); max-width: 420px; }
  .scrim { position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 10; animation: fa-fade 0.15s ease; }
  .dialog {
    position: fixed; z-index: 11; left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: min(400px, calc(100vw - 32px)); padding: 24px; animation: fa-pop 0.18s ease;
  }
  .dialog h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; }
  .dialog p { margin: 0 0 20px; color: var(--fa-muted); }
  .dialog-buttons { display: flex; justify-content: flex-end; gap: 8px; }

  /* Loading skeleton */
  .sk {
    border-radius: 8px;
    background: linear-gradient(90deg, var(--fa-skeleton) 0%,
      color-mix(in srgb, var(--fa-skeleton) 55%, var(--fa-card)) 50%, var(--fa-skeleton) 100%);
    background-size: 200% 100%; animation: fa-shimmer 1.4s ease-in-out infinite;
  }
  .sk-image { width: 100%; height: 100%; min-height: 120px; }
  .sk-line { height: 14px; width: 70%; }
  .sk-line.short { width: 40%; }
  .sk-line.big { height: 26px; width: 55%; }
  .sk-line.title { height: 28px; width: 80%; }
  .sk-action { height: 96px; border-radius: var(--fa-radius); }
  .loading .hero { background: var(--fa-card); border-radius: var(--fa-radius); border: 1px solid var(--fa-divider); }
  .skeleton-tile { cursor: default; gap: 10px; }
  .loading .actions { grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); }

  @keyframes fa-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  @keyframes fa-spin { to { transform: rotate(360deg); } }
  @keyframes fa-fade { from { opacity: 0; } }
  @keyframes fa-pop { from { opacity: 0; transform: translate(-50%, -46%); } }
  @media (prefers-reduced-motion: reduce) {
    .sk, .spinner { animation-duration: 3s; }
    .image-wrap img, .bar > div, .toggle, .toggle span { transition: none; }
  }

  @media (max-width: 720px) {
    .hero { grid-template-columns: 1fr; }
    .hero h1 { font-size: 24px; }
    .content { padding: 12px; gap: 12px; }
    .actions { grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 8px; }
    .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .tile { padding: 12px; }
    .tile-value { font-size: 20px; }
    .tile.tires { grid-column: span 2; }
    .wheels { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
    .wheel { flex-direction: column; gap: 2px; }
  }
`;

if (!customElements.get("ford-assistant-panel")) {
  customElements.define("ford-assistant-panel", FordAssistantPanel);
}
