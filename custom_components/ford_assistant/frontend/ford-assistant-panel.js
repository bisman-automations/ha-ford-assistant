/*
 * Ford Assistant sidebar dashboard.
 *
 * A plain web component (no build step, no external libraries) that Home
 * Assistant loads as a custom panel. It asks the backend once for the vehicles
 * and their entity IDs (`ford_assistant/vehicles`), then renders from the live
 * `hass` object it's given and calls services through it.
 */

const STORAGE_KEY = "ford-assistant-panel:vehicle";
const PENDING_TIMEOUT = 45000; // Ford commands can take 30+ seconds
const BAD = new Set(["unknown", "unavailable", "", null, undefined]);

const FEATURE_GROUPS = [
  { title: "Security", keys: ["auto_lock", "night_lock", "door_open_alert", "alarm_alert"] },
  {
    title: "Remote start",
    keys: ["precondition", "work_prompt", "auto_extend", "remote_start_activity"],
  },
  {
    title: "Alerts",
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
  { title: "Garage", keys: ["garage_open", "garage_close"] },
  { title: "Notifications", keys: ["status_activity", "quiet_hours", "clear_resolved"] },
];

const TIRES = [
  ["frontLeft", "FL"],
  ["frontRight", "FR"],
  ["rearLeft", "RL"],
  ["rearRight", "RR"],
];

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
    this._render();
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
      this._error = (err && err.message) || String(err);
    }
    this._render(true);
  }

  get _vehicle() {
    return (this._vehicles || []).find((v) => v.entry_id === this._selected) || null;
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

  _signatureFor(vehicle) {
    if (!vehicle) return "";
    const ids = [
      ...Object.values(vehicle.ford),
      ...Object.values(vehicle.assistant.switch),
      ...Object.values(vehicle.assistant.number),
      ...Object.values(vehicle.assistant.sensor),
      vehicle.garage,
      vehicle.home_zone,
    ];
    return ids
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
    if (this._error) {
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
      <div class="loading" aria-busy="true" aria-label="Loading your vehicles">
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
      <h2>Couldn't load your vehicles</h2>
      <p>${esc(this._error)}</p>
      <button class="button primary" data-action="retry">Try again</button>
    </div>`;
  }

  _emptyView() {
    return `<div class="message card">
      <ha-icon icon="mdi:car-off"></ha-icon>
      <h2>No vehicles yet</h2>
      <p>Add Ford Assistant for a vehicle from the Ford integration to see it here.</p>
      <button class="button primary" data-action="navigate"
        data-path="/config/integrations/integration/ford_assistant">Open Ford Assistant</button>
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
    if (alarmGoing) return { text: "Alarm!", tone: "error", icon: "mdi:alarm-light" };
    if (running) return { text: "Running", tone: "info", icon: "mdi:engine" };
    if (driving) return { text: "Driving", tone: "info", icon: "mdi:steering" };
    if (doorsOpen) return { text: "Door open", tone: "error", icon: "mdi:car-door" };
    if (lock === "unlocked")
      return { text: "Unlocked", tone: home ? "warning" : "error", icon: "mdi:lock-open-variant" };
    if (lock === "locked") return { text: "Locked", tone: "success", icon: "mdi:lock" };
    return { text: "Parked", tone: "neutral", icon: "mdi:car" };
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
    if (!tracker || BAD.has(tracker.state)) return "Unknown";
    if (this._atHome(v)) return "Home";
    if (tracker.state === "not_home") return "Away";
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
      <section class="actions">${this._actions(v)}</section>
      <section class="grid">${this._tiles(v)}</section>
      ${this._featuresView(v)}
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

  _actions(v) {
    const f = v.ford;
    const items = [];
    const lock = this._value(f.lock);
    if (f.lock) {
      items.push(
        lock === "locked"
          ? this._action("unlock", "mdi:lock-open-variant", "Unlock", BAD.has(lock))
          : this._action("lock", "mdi:lock", "Lock", BAD.has(lock)),
      );
    }
    if (f.remote_start) {
      const running = this._value(f.remote_start) === "on";
      items.push(
        running
          ? this._action("stop", "mdi:engine-off", "Stop", false, "active")
          : this._action("start", "mdi:engine", "Start", BAD.has(this._value(f.remote_start))),
      );
      // Button entities stay "unknown" until first pressed, so only hide unavailable ones.
      if (running && f.extend && this._usable(f.extend)) {
        items.push(this._action("extend", "mdi:timer-plus", "Extend"));
      }
    }
    if (f.honk && this._usable(f.honk)) {
      items.push(this._action("honk", "mdi:car-light-high", "Honk & flash"));
    }
    if (v.garage && this._state(v.garage)) {
      const garage = this._value(v.garage);
      items.push(
        garage === "open" || garage === "opening"
          ? this._action("garage_close", "mdi:garage", "Close garage")
          : this._action("garage_open", "mdi:garage-open", "Open garage"),
      );
    }
    if (f.refresh && this._usable(f.refresh)) {
      items.push(this._action("refresh", "mdi:refresh", "Refresh"));
    }
    return items.join("");
  }

  _usable(entityId) {
    const state = this._state(entityId);
    return !!state && state.state !== "unavailable";
  }

  _action(action, icon, label, disabled = false, extra = "") {
    const pending = this._pending.has(action);
    return `<button class="action ${extra} ${pending ? "pending" : ""}" data-action="${action}"
        ${disabled || pending ? "disabled" : ""} aria-label="${esc(label)}">
      <span class="action-icon">${
        pending ? `<span class="spinner" aria-hidden="true"></span>` : `<ha-icon icon="${icon}"></ha-icon>`
      }</span>
      <span class="action-label">${esc(pending ? "Sending…" : label)}</span>
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
          label: isFuel ? "Fuel" : "Battery",
          value: level === null ? "—" : `${Math.round(level)}%`,
          detail: range === null ? "" : `${Math.round(range)} ${unit} range`,
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
        charging === "IN_PROGRESS" ? "Charging" : !BAD.has(plug) ? humanize(plug) : "—";
      tiles.push(
        this._tile({
          entity: f.ev_charging || f.ev_plug,
          icon: charging === "IN_PROGRESS" ? "mdi:ev-station" : "mdi:ev-plug-type1",
          label: "Charging",
          value,
          detail: !BAD.has(charging) && charging !== "IN_PROGRESS" ? humanize(charging) : "",
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
          label: "Remote start",
          value: minutes ? `${Math.round(minutes)} min left` : "Running",
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
            .map(([key]) => humanize(key))
        : [];
      tiles.push(
        this._tile({
          entity: f.doors,
          icon: open.length ? "mdi:car-door" : "mdi:car-door-lock",
          label: "Doors",
          value: open.length ? `${open.length} open` : doors ? "All closed" : "—",
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
          label: "Windows",
          value: BAD.has(windows) ? "—" : windows,
          tone: windows === "Open" && !this._atHome(v) ? "warning" : "",
        }),
      );
    }

    if (f.tracker) {
      tiles.push(
        this._tile({
          entity: f.tracker,
          icon: this._atHome(v) ? "mdi:home" : "mdi:map-marker",
          label: "Location",
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
          label: "Oil life",
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
          label: "12V battery",
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
          label: "Alarm",
          value: BAD.has(alarm) ? "—" : humanize(alarm),
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
          label: "Warning lights",
          value: on.length ? `${on.length} on` : indicators ? "None" : "—",
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
          label: "Outside",
          value: this._format(f.temperature),
        }),
      );
    }

    if (f.odometer) {
      tiles.push(
        this._tile({
          entity: f.odometer,
          icon: "mdi:counter",
          label: "Odometer",
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
      return `<div class="wheel ${bad ? "bad" : ""}"><span>${short}</span>
        <strong>${esc(attrs[key] !== undefined ? attrs[key] : "—")}</strong></div>`;
    }).join("");
    return `<button class="tile tires ${warn ? "warning" : ""}" data-action="more-info"
        data-entity="${esc(entityId)}">
      <div class="tile-head"><ha-icon icon="mdi:car-tire-alert"></ha-icon><span>Tire pressure</span></div>
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
      return rows ? `<div class="group"><h3>${esc(group.title)}</h3>${rows}</div>` : "";
    }).join("");
    if (!groups) return "";
    const settings = v.assistant_device_id
      ? `<button class="button" data-action="navigate"
          data-path="/config/devices/device/${esc(v.assistant_device_id)}">
          <ha-icon icon="mdi:tune-variant"></ha-icon>Thresholds &amp; times</button>`
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
          <button class="button" data-action="cancel">Cancel</button>
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
    const confirms = {
      unlock: {
        title: `Unlock ${v.name}?`,
        text: "All doors will unlock.",
        label: "Unlock",
      },
      start: {
        title: `Start ${v.name}?`,
        text: "The engine will start remotely and run until the timer ends or you stop it.",
        label: "Start",
      },
      garage_open: {
        title: "Open the garage?",
        text: "The garage door will open.",
        label: "Open",
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
    }, PENDING_TIMEOUT);
    this._pending.set(action, { timer, watch, from });
    this._render(true);
    Promise.resolve(this._hass.callService(domain, service, { entity_id: entityId })).catch((err) => {
      clearTimeout(timer);
      this._pending.delete(action);
      this._toast(`Couldn't ${action.replace("_", " ")}: ${(err && err.message) || err}`);
      this._render(true);
    });
  }

  _resolvePending() {
    // A command is done once the entity it affects reports a new state.
    for (const [action, pending] of this._pending) {
      const state = this._state(pending.watch);
      if (state && state.last_updated !== pending.from) {
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
