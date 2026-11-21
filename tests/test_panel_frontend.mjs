// Node tests for the dashboard's update gate.
// Run with: node --test tests/*.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const SOURCE = readFileSync(
  new URL("../custom_components/ford_assistant/frontend/ford-assistant-panel.js", import.meta.url),
  "utf8",
);

function load() {
  const defined = {};
  const listeners = {};
  const document = {
    hidden: false,
    addEventListener: (type, fn) => {
      listeners[type] = fn;
    },
    removeEventListener: (type) => {
      delete listeners[type];
    },
    createElement: () => ({}),
  };
  const context = {
    console,
    setTimeout,
    clearTimeout,
    HTMLElement: class {
      attachShadow() {
        this.shadowRoot = { querySelector: () => null, innerHTML: "" };
        return this.shadowRoot;
      }
      dispatchEvent() {}
    },
    customElements: {
      get: (name) => defined[name],
      define: (name, cls) => {
        defined[name] = cls;
      },
    },
    window: { localStorage: { getItem: () => null, setItem: () => {} } },
    document,
  };
  vm.createContext(context);
  vm.runInContext(SOURCE, context);
  return { Panel: defined["ford-assistant-panel"], document, listeners };
}

const VEHICLE = {
  entry_id: "e1",
  name: "My Car",
  ford: { lock: "lock.my_car_lock" },
  assistant: {
    switch: {},
    number: {},
    time: {},
    select: { driving_mode: "select.my_car_driving_mode" },
    sensor: {},
    binary_sensor: {},
  },
  garage: null,
  home_zone: "zone.home",
};

function hassWith(states) {
  return { states, callWS: async () => ({ vehicles: [VEHICLE] }), user: { is_admin: true } };
}

test("draws only when the vehicle's own entities change, and not while hidden", () => {
  const { Panel, document, listeners } = load();
  const panel = new Panel();
  panel._load = () => {};
  panel._vehicles = [VEHICLE];
  panel._selected = "e1";
  let draws = 0;
  panel._render = () => {
    draws += 1;
  };
  const lock = { state: "locked" };
  const mode = { state: "normal" };
  const zone = { state: "1" };
  panel.hass = hassWith({ "lock.my_car_lock": lock, "select.my_car_driving_mode": mode, "zone.home": zone });
  assert.equal(draws, 1);

  // Something elsewhere in the house: nothing to draw.
  panel.hass = hassWith({ "lock.my_car_lock": lock, "select.my_car_driving_mode": mode, "zone.home": zone, "light.kitchen": {} });
  assert.equal(draws, 1);

  // Who's driving changes: drawn.
  const valet = { state: "valet" };
  panel.hass = hassWith({ "lock.my_car_lock": lock, "select.my_car_driving_mode": valet, "zone.home": zone });
  assert.equal(draws, 2);

  // Hidden: the change waits until the page is seen again, drawn once.
  document.hidden = true;
  const unlocked = { state: "unlocked" };
  panel.hass = hassWith({ "lock.my_car_lock": unlocked, "select.my_car_driving_mode": valet, "zone.home": zone });
  panel.hass = hassWith({ "lock.my_car_lock": { state: "locked" }, "select.my_car_driving_mode": valet, "zone.home": zone });
  assert.equal(draws, 2);
  document.hidden = false;
  listeners.visibilitychange();
  assert.equal(draws, 3);
  listeners.visibilitychange();
  assert.equal(draws, 3);
});
