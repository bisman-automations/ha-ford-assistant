# Ford Assistant: notes for Claude

Ford Assistant (`ford_assistant`) is a HACS custom integration that's a companion to
marq24's Ford integration (`fordpass`, https://github.com/marq24/ha-fordpass). It adds
automations and alerts on top of the Ford integration's entities. It began as the
"FordPass – Vehicle Assistant" blueprint. Say "the Ford integration", not "FordPass": Ford
renamed the app, though the domain is still `fordpass`.

## Ground rules

- **Never import from or patch the Ford integration.** Only use its public surface:
  entity states and attributes, and service calls (`lock.lock`, `switch.turn_on`,
  `button.press`, …).
- **Find Ford entities by unique_id, never by entity_id.** The Ford integration builds
  unique_ids as `fordpass_uid_{vin}_{key}` (lower-case). The role → (platform, key) map
  is `FORD_ENTITY_KEYS` in `const.py`, resolved in `discovery.resolve_entities`. Entities
  a vehicle doesn't have are simply missing, so code must handle any role being absent.
  Only `lock` and `tracker` are required (`REQUIRED_ROLES`).
- **No user-specific details in the repo.** Never put real VINs, entity IDs, device IDs,
  zone names, phone names or other account details in code, tests, the README or the
  changelog; use placeholders like `1FTEST00000000001`.
- **Support HA 2026.2 (the `hacs.json` minimum) through the latest release.** Use
  `compat.py` for device registry calls (see below), and check APIs exist in both.

## Layout (`custom_components/ford_assistant/`)

| File | What it does |
| --- | --- |
| `__init__.py` | Setup/unload. A missing lock or tracker raises a repair issue and `ConfigEntryNotReady`. |
| `config_flow.py` | Pick a Ford vehicle → optionally import a blueprint automation → phones, zones, weather, to-do, garage. The options flow (`OptionsFlowWithReload`) changes those plus days and alarm states. |
| `controller.py` | `FordAssistantController`: all runtime logic for one vehicle (listeners, timers, notifications, alerts, commands). Settings persist through a `Store`. |
| `status.py` | The always-on vehicle status Live Activity (`StatusActivity`). |
| `panel.py` | The sidebar dashboard: registers the panel (only when the frontend is loaded), serves `frontend/`, and the `ford_assistant/vehicles` websocket command. |
| `frontend/ford-assistant-panel.js` | The dashboard web component. Plain JS with no build step or external libraries; it renders from the live `hass` object and calls services through it. |
| `logic.py` | Pure helpers with no HA state access; put testable logic here. |
| `discovery.py` | Finds Ford vehicles, the Ford device and the Ford entities. |
| `compat.py` | Device registry helpers that work before and after HA 2026.8. |
| `importer.py` | Converts blueprint automation inputs into Ford Assistant settings. |
| `entity.py` | Base entity and `device_info()`. |
| `switch.py` / `number.py` / `time.py` / `sensor.py` | Feature switches, thresholds/delays, schedule times, last-event sensor. |
| `const.py` | Domain, Ford keys, `FEATURES`, `NUMBERS`, `TIMES`, defaults. |
| `strings.json` + `translations/en.json` | UI text. **Keep the two identical.** |
| `icons.json` | One icon per entity translation key. |
| `brand/` | Integration icons (`icon`, `dark_icon`, each at 1x and @2x). |

## How settings work

- **Features, numbers and times are entities, not options.** Add one by adding a key to
  `FEATURES` / `NUMBERS` (a `NumberSpec`) / `TIMES` in `const.py`, then add its name to
  `strings.json` **and** `translations/en.json`, and its icon to `icons.json`. Values
  are stored by the controller's `Store`, not in the config entry.
- **EV-only settings** go in `EV_FEATURES` / `EV_NUMBERS` / `EV_TIMES`. They're only
  created when the vehicle has EV sensors (`controller.is_electric`).
- **Options** (phones, zones, weather, to-do, garage, days, alarm states) live in
  `entry.options` and are read with `controller.options`.
- New features that change behavior on upgrade should default to off unless clearly safe.

## Notifications and Live Activities

- Send through `controller._notify(kind, title, message, ...)`. It handles tags
  (`ford-{kind}-{vin}`), action buttons, quiet hours, the `ford_assistant_alert` event,
  the last-event sensor and tracking what's shown so `_clear(kind)` can remove it later.
- Notify targets come from the selected Companion app devices (`notify.mobile_app_*`
  services), looked up from the mobile_app config entry's `device_name`.
- Urgency: `critical=True` only for the alarm; `time_sensitive=True` for door alerts and
  charging faults; everything else is normal and can be held during quiet hours.
- Latched alerts fire once and re-arm when the condition clears (`_latch`,
  `percent_alert`, `state_alert` in `logic.py`). Clearing a latch clears the notification.
- Live Activity payloads follow the Companion app docs
  (https://companion.home-assistant.io/docs/notifications/live-activities/), with the same
  shape as the `ha-appliance-live-activity` integration: `live_update`, `tag`,
  `critical_text`, `progress`/`progress_max`, `chronometer` + `when` + `when_relative`.
  **iOS Live Activities don't support action buttons** (Android does), iOS ends them after
  8 hours, and frequent updates get throttled. So only push on visible changes and let
  `chronometer` count down on the phone.

## Ford integration quirks

- Door status values are `CLOSED`, `AJAR`, `OPEN`, …; the doors sensor also has HA's own
  `icon`/`friendly_name` attributes, so `open_doors()` only counts upper-case values.
- The update sent as the ignition turns off often reports the driver's door `AJAR`, and the
  vehicle may not report again once it closes. The controller presses the Ford
  **Request refresh** button once, 2 minutes after parking, to confirm.
- The remote start countdown is reported in minutes (`unit_of_measurement: min`); use
  `countdown_minutes()` to handle other units.
- Charging: `IN_PROGRESS` → `STOPPED` means done; `FAULT` / `STATION_NOT_DETECTED` are
  faults. Plug states: `CONNECTED` / `DISCONNECTED`.
- Reference copy of the Ford integration for checking keys and values:
  `git clone --depth 1 https://github.com/marq24/ha-fordpass`
  (`const_tags.py`, `fordpass_handler.py`).

## Devices (HA 2026.8+ vs older)

HA 2026.8 made devices belong to one config entry; devices from different integrations
sharing an identifier or connection are shown as **Linked devices**.

- On 2026.8+, Ford Assistant has its own device with identifiers
  `{(ford_assistant, vin), (fordpass, vin)}`, so it links to the Ford vehicle's device.
- On older HA, sharing an identifier merges devices, so `device_info()` passes only
  `(fordpass, vin)` and the entities join the Ford device.
- Always go through `compat.py` (`PER_ENTRY_DEVICES`, `devices_with_identifier`,
  `device_in_domain`, `device_entry_ids`, `all_devices`). **Don't call
  `device_registry.async_get_device`, index `registry.devices`, or read
  `DeviceEntry.config_entries`.** They're deprecated in 2026.10 and stop working in 2027.
  To find the Ford vehicle's own device, use `discovery.ford_device()`; on 2026.8+ a plain
  identifier lookup can return Ford Assistant's device instead.

## Dashboard

- The panel is a vanilla custom element (`ford-assistant-panel`) using only HA CSS variables and
  HA's own `ha-icon` / `ha-menu-button`, so it themes and works offline. Keep it dependency-free.
- It asks the backend once for vehicles and entity IDs (`ford_assistant/vehicles`); everything
  else comes from `hass.states`. Add new Ford roles to `FORD_ENTITY_KEYS` and they're sent along.
- Unlock, remote start and opening the garage must confirm first. Button entities sit at
  `unknown` until pressed, so only treat `unavailable` as unusable.
- Check `node --check` on the JS, and render it in Chromium with a fake `hass` (Playwright is
  available) in light and dark themes and at phone width before shipping UI changes.
- Tests don't have the frontend package, so the panel isn't registered there; `test_panel.py`
  patches `panel_custom` and the HTTP static path to test registration.

## Testing

```bash
python -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest -q
```

- Python 3.13 installs HA 2026.2 (the oldest supported); Python 3.14 installs the latest
  HA. **Run the tests on both** when touching device registry or other HA APIs. CI runs
  both (`tests (3.13)` and `tests (3.14)`).
- Tests use `pytest-homeassistant-custom-component`. The `ford` fixture in
  `tests/test_init.py` fakes a Ford vehicle and a phone; reuse it (and `_setup`,
  `_entity_id`, `_ours`, `_clears`) from other test files.
- Look up Ford Assistant's own entities by unique_id with `_ours(hass, platform, key)`,
  not hard-coded entity IDs; they differ between HA versions.
- For timers, call `hass.async_block_till_done()` before advancing time. Code that reads
  `dt_util.utcnow()` needs the `freezer` fixture (`freezer.tick(...)` then
  `async_fire_time_changed(hass)`).
- Lint: `ruff check custom_components tests --select F,E9,B` (tests may re-import the
  `ford` fixture, so ignore F811 there).
- Every new feature or fix gets a test.

## Releases

1. Bump `version` in `manifest.json` (semver: features → minor, fixes → patch).
2. Add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md` (Keep a Changelog:
   Added / Changed / Fixed), written for users, not developers.
3. Update `README.md` when behavior, entities or requirements change.
4. Commit and push to `main`. CI (`validate.yaml`: hassfest, HACS, tests on 3.13 and
   3.14) must pass.
5. `draft-release.yml` creates or refreshes a draft GitHub release for the manifest
   version on every push to `main`. The maintainer publishes it, which creates the tag.
   Claude can't create releases or tags from its sessions.
