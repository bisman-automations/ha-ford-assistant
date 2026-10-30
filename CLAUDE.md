# Ford Assistant: notes for Claude and other coding agents

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
- **Support HA 2026.8 (the `hacs.json` minimum) through the latest release.** Use
  `compat.py` for device registry calls (see below), and check APIs exist in both.
- **Access:** admins plus the people an admin picks (`access.py`, the same model as
  TV Mgmt). The `ford_assistant/vehicles` websocket command uses `@require_access`, the
  access commands `require_admin`, and Ford Assistant's switches, numbers and times call
  `async_ensure_allowed`. The Ford integration's own entities keep HA's permissions.

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

## Devices

HA 2026.8 made devices belong to one config entry; devices from different integrations
sharing an identifier or connection are shown as **Linked devices**.

- Ford Assistant has its own device with identifiers
  `{(ford_assistant, vin), (fordpass, vin)}`, so it links to the Ford vehicle's device.
- Always go through `compat.py` (`devices_with_identifier`, `device_in_domain`,
  `device_entry_ids`, `all_devices`). `registry.devices` is a mapping on 2026.8 and an
  iterable of devices from 2026.9; `all_devices` handles both. **Don't call
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

Run the shared checks at the end of this file.

- `requirements_test_min.txt` (Python 3.14) installs HA 2026.8, the oldest supported;
  `requirements_test.txt` (Python 3.14) installs the latest. **Run the tests on both**
  when touching device registry or other HA APIs. CI runs both.
- Tests use `pytest-homeassistant-custom-component`. The `ford` fixture in
  `tests/test_init.py` fakes a Ford vehicle and a phone; reuse it (and `_setup`,
  `_entity_id`, `_ours`, `_clears`) from other test files.
- Look up Ford Assistant's own entities by unique_id with `_ours(hass, platform, key)`,
  not hard-coded entity IDs; they differ between HA versions.
- For timers, call `hass.async_block_till_done()` before advancing time. Code that reads
  `dt_util.utcnow()` needs the `freezer` fixture (`freezer.tick(...)` then
  `async_fire_time_changed(hass)`).
- Lint with the shared ruff settings in `pyproject.toml`. Tests import the `ford`
  fixture from `test_init.py`, which ruff's F811 ignores in `tests/` for that reason.
- Every new feature or fix gets a test.

## Docs

- Update `README.md` when behavior, entities or requirements change.
- Write CHANGELOG entries for users, not developers.

<!-- BEGIN bisman-automations shared rules -->
<!-- This block is the same in every bisman-automations repo. Edit it in
     bisman-automations/.github (templates/CLAUDE.shared.md) and copy it to
     every repo; the Validate workflow's "standards" job checks it matches. -->

## Shared rules (every bisman-automations repo)

### Releases

- The version lives in `custom_components/<domain>/manifest.json`. Anything
  else that repeats it is called out in the repo-specific notes below and is
  bumped in the same commit.
- Versions follow [Semantic Versioning](https://semver.org): patch for fixes,
  translations, docs and CI; minor for new features, options or entities;
  major when something users rely on is removed or renamed (entities,
  services, events, options) or setup has to be redone.
- Check what is released before choosing a version:
  `git ls-remote --tags origin | awk -F/ '{print $3}' | sort -V | tail -1`
  (`sort -V`: plain sorting puts `v1.10.0` before `v1.9.0`). Never add
  changes to a released version. If the manifest version has no tag yet,
  add to its CHANGELOG section instead of bumping again.
- Every push to `main` ships as a release. In that same commit, named
  `Release X.Y.Z`, bump the manifest version and write the notes directly
  under a new `## [X.Y.Z] - YYYY-MM-DD` heading in `CHANGELOG.md` (Keep a
  Changelog: Added, Changed, Deprecated, Removed, Fixed, Security), with
  that version's compare link at the bottom. There is no `## [Unreleased]`
  section and no `[Unreleased]:` compare link. New work is not collected
  under a holding heading and moved later; the release commit is where the
  heading and the entries are written. The standards check fails if a
  `## [Unreleased]` heading is present.
- Ask Donavan before every push. Push fast-forward only: never force-push,
  rebase or amend anything already pushed, or rewrite history in any other
  way. Rewriting history orphans the release tags (it broke drafting in
  ha-button-actions).
- Pushing to `main` runs **Draft release**, which creates or refreshes a
  draft `vX.Y.Z` with that version's CHANGELOG section as the notes, the
  commits since the last release and `<domain>.zip`. **Donavan publishes
  the draft himself**, and publishing creates the tag. Never create or push
  tags, publish releases, or edit published releases.
- Publishing runs **Release check**: the tag must match the manifest version
  and the CHANGELOG, and be on `main`. If it fails, fix it with a new patch
  release, not by moving the tag.

### Commits

- Author commits as `Donavan Becker <donavan.becker@icloud.com>` (set
  `git config user.name` / `user.email` in the clone). HACS's
  default-repository check needs the submitter to have a fair share of the
  commits. Credit an AI assistant with a `Co-Authored-By:` trailer if you
  like, never as the author.
- Subject lines are plain, imperative and say what changed for the user
  ("Show Pico remotes as unavailable when Lutron isn't running"). No
  `fix:`/`feat:` prefixes. Release commits are "Release X.Y.Z".
- Commit and push only when asked.

### CI (shared workflows)

- `.github/workflows/` holds four thin callers of the reusable workflows in
  [bisman-automations/.github](https://github.com/bisman-automations/.github):
  `test.yml` (lint, frontend, pytest on the oldest supported and the newest
  Home Assistant, plus the upcoming one as information only), `validate.yml`
  (hassfest, HACS, standards), `draft-release.yml` and `release-check.yml`.
  Don't add jobs to the callers. Use the shared workflow's inputs, or change
  the shared workflow so every repo gets the improvement.
- `requirements_test.txt` leaves `pytest-homeassistant-custom-component`
  unpinned (newest Home Assistant) and pins ruff (and mypy where used).
  `requirements_test_min.txt` pins the harness release for the minimum in
  `hacs.json`: the newest harness release of that month. CI fails if they
  drift apart.
- Raising the minimum Home Assistant means changing, together: `hacs.json`,
  `requirements_test_min.txt`, `python-min` in `test.yml` (3.13 up to
  2026.2, 3.14 from 2026.3), the README's Home Assistant badge, and a
  CHANGELOG entry.
- Home Assistant 2026.3 and newer need Python 3.14 (3.14.2+).
- The published hassfest rejects `categories` in `manifest.json` and Pillow
  in `requirements`. Leave both out.
- Dependabot (`.github/dependabot.yml`) proposes action and pinned-tool
  updates weekly. It ignores the test harness on purpose.
- Test and Validate also run every Thursday, the day after Home Assistant's
  betas come out. The **next** test job (newest pre-release harness) is
  information only: when it fails, fix the cause before that release ships.

### Before saying work is done

Run from the repo root, in a Python 3.14 venv with `requirements_test.txt`
installed:

```
ruff check .
ruff format --check .
pytest
```

Also run `node --test tests/*.mjs` when the repo has Node tests, mypy when
the repo-specific notes list it, and the tests in a second venv with
`requirements_test_min.txt` when a change could behave differently on the
oldest supported Home Assistant. The standards check (also in CI) is
`python <path to bisman-automations/.github>/scripts/check_repo.py .`.

### Code and docs

- Support every Home Assistant from the `hacs.json` minimum to the newest
  release. Check for deprecations in the newest release and the beta.
- Keep entity IDs, unique IDs, service names and event names stable. When
  one has to change, migrate it and say so under Changed in the CHANGELOG.
- `strings.json` and `translations/en.json` hold the same keys. Home
  Assistant reads only `translations/`, so change both in the same commit.
- Never put personal details in the repo (README, CHANGELOG, code, tests,
  screenshots): no names, addresses, account or device identifiers, or real
  entity IDs. Use placeholders such as `light.living_room`.
- `README.md` is user documentation with the standard header (badges,
  Marketplace, HACS and "add integration" My buttons) and sections
  Installation, Setup, ..., Troubleshooting, Development, License. Use plain
  language and show names, not entity IDs, wherever the UI does.
<!-- END bisman-automations shared rules -->
