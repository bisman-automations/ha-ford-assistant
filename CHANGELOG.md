# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.0] - 2026-11-14

### Added

- **FordPass China.** Ford Assistant now also works with the [FordPass China](https://github.com/RockJesus/ha-fordpass-cn) integration: pick the car from either integration during setup. Alerts, the sidebar dashboard, Live Activities and Who's driving run on its readings. Because FordPass China splits the car over many entities, reports them in Chinese and has no lock entity, Ford Assistant adds a few bridge entities for such a car: a vehicle lock (from its lock status and lock and unlock buttons), and doors, windows, tire pressure, alarm, ignition, remote start, fuel, battery, charging and a honk-and-flash button. FordPass China has no 12V battery percentage, outside temperature or warning-light count, so those three checks are left out for it. Thanks to RockJesus for this.
- **Simplified Chinese.** Ford Assistant's setup, settings, entity names and repair messages are now also in Simplified Chinese. Notifications and the sidebar dashboard are still in English.

## [1.7.2] - 2026-11-14

### Changed

- **Renaming an entity keeps it running.** From Home Assistant 2026.11, when you change one of this integration's entity IDs, the entity moves to its new ID in place instead of being removed and added again, as Home Assistant now expects. Everything keeps working the same.

### Fixed

- **Tests pass on weekends.** A test of preconditioning in Service mode assumed the day was a weekday, so it failed on Saturdays and Sundays. Nothing changes for you.

## [1.7.1] - 2026-11-13

### Changed

- **Smoother updates.** Each kind of entity now tells Home Assistant how many updates it can take at once, as Home Assistant recommends. Nothing changes in how anything looks or works.

## [1.7.0] - 2026-11-10

### Added

- **Who's driving.** Each vehicle has a **Who's driving** list: **Household**, **Service** or **Guest**. It is remembered across restarts.
  - **Household** is everyday driving. Under **Configure**, choose which Home Assistant people are household drivers, then for each person which alerts they get, which phones those alerts go to, and which actions are enabled for them. While one of them is the **Active driver**, only that profile is used. With nobody selected, every feature follows its own switch, as before.
  - **Active driver** can be chosen by hand, or filled in when exactly one household person (or their phone) leaves home within 15 minutes of the vehicle leaving. More than one person, or nobody, and Ford Assistant leaves the choice alone. Parking at home clears it. A choice you make yourself stays until then. The Ford integration doesn't report phone-as-a-key, so a person's own device tracker is the phone signal.
  - **Service** is for a workshop visit. Every alert stays on. Every action is blocked: auto-lock, night lock, lock and unlock commands, honk, remote start and its routines, and the garage. Asking the vehicle for a fresh status is not blocked.
  - **Guest** is for a borrowed or lent vehicle, or any other driver. Safety alerts stay on (alarm, doors, windows, fuel, 12V battery, tires, warning lights, charging) and so does the vehicle status Live Activity. Oil life, the plug-in reminder and the remote-start countdown stay off. The car can still be locked, unlocked, honked and auto-locked. Night lock, remote start, the morning and leaving-work routines, and the garage are blocked.
  - Both modes can return to **Household** on their own after a duration you set. The countdown survives a restart. Set the duration to 0 on the **Set who's driving** action to stay until someone changes it.
  - Checklists for both modes, and each driver's profile, are editable. The feature switches are not changed, so leaving the mode puts them back.
  - A **Driving status** sensor and the attributes on **Who's driving** show the mode, the active driver, and the actions and alerts that are allowed or blocked. **Automations suppressed** is on while any action is blocked. Changing mode fires `ford_assistant_driving_mode_changed`.
  - A household driver whose person is linked to their Home Assistant user can open the dashboard. Admins, and anyone an admin checks under **Who can use Ford Assistant**, still can.

## [1.6.4] - 2026-11-10

### Changed

- **Install from the Marketplace by searching for Ford Assistant.** Home Assistant 2026.11 renames HACS to the Marketplace, so the install steps start by searching the Marketplace. Searching HACS stays for Home Assistant 2026.10 and older, and adding the repository as a custom repository remains the fallback.
- **Ruff 0.17.4.** Linting uses the current Ruff release.

## [1.6.3] - 2026-11-06

### Added

- **French.** Ford Assistant is now in French as well as English ([#4](https://github.com/bisman-automations/ha-ford-assistant/issues/4)):
  - setup, settings and the switch, number and time names;
  - the dashboard, which follows each person's own language in Home Assistant;
  - notifications, their buttons and the vehicle status Live Activity, which follow Home Assistant's language (**Settings → System → General**).

  Readings Ford Assistant doesn't have a word for are spelled out in English.

## [1.6.2] - 2026-11-06

### Fixed

- **Locking… and Unlocking… on the vehicle card.** After you tap **Lock** or **Unlock**, the card and the button say **Locking…** or **Unlocking…** until the vehicle confirms it, instead of the lock status disappearing and coming back later ([#5](https://github.com/bisman-automations/ha-ford-assistant/issues/5)). The same shows when the vehicle is locked or unlocked from somewhere else, such as the Ford app, and a jammed lock now shows as **Lock jammed**.

## [1.6.1] - 2026-10-30

### Changed

- **Install from the Marketplace.** The README now explains how to install from the Marketplace that replaces HACS in Home Assistant 2026.11, with its own button. The HACS steps stay for Home Assistant 2026.10 and older, and an install you already have moves over by itself.

## [1.6.0] - 2026-10-30

### Added

- **Who can use Ford Assistant,** at the bottom of the dashboard for admins. Admins always can; an admin checks anyone else who should. Someone who isn't allowed gets a page saying so.

### Changed

- **Requires Home Assistant 2026.8 or newer.**
- **Only admins see the dashboard until an admin lets someone else in.** It shows where the vehicle is and can unlock and start it, and before this release anyone with a Home Assistant login could open it. If people who aren't admins use it, check their names under **Who can use Ford Assistant**. Ford Assistant's own switches, thresholds and times follow the same rule; automations always can.
- The README follows the same layout as the other bisman-automations integrations: a button that opens it in HACS, a button that starts setup, and troubleshooting steps for debug logs and diagnostics.
- Each release now includes `ford_assistant.zip` for installing without HACS.
- The changelog no longer keeps an Unreleased section, and the agent notes follow the updated shared release rules.

### Fixed

- **The garage no longer opens when you're already home.** It used to open whenever the vehicle's location changed to home, even when that update came in late (after you'd parked and used the door) or when Home Assistant restarted. Now it only opens for an arrival reported while you're still driving, never in the first 3 minutes after Home Assistant or Ford Assistant starts, not when the door was opened or closed in the last 10 minutes, and only once per arrival.
- **Activity shows that Ford Assistant opened or closed the garage,** and why, on the garage door's Activity.
- **Ford Assistant works on Home Assistant 2026.8.** It couldn't find the Ford vehicle there, so setup failed; 2026.9 and newer weren't affected.

## [1.5.0] - 2026-10-23

### Added

- **Sidebar dashboard.** A Ford Assistant page in the sidebar, added automatically once a vehicle is set up. It shows the vehicle's picture from the Ford integration and a status chip (Locked, Unlocked, Door open, Running, Driving or Alarm). There are controls for lock and unlock, remote start, stop and extend, honk and flash, the garage door and refresh. Unlock, Start and opening the garage ask for confirmation, and buttons show "Sending…" until the vehicle responds. Status tiles cover fuel or battery with range, charging, doors, windows, location, tire pressures, oil life, 12V battery, alarm, warning lights, temperature and odometer, and turn amber or red when something needs attention; tap one for details. Every Ford Assistant feature switch is on the page, grouped by topic, and there's a tab per vehicle when you have more than one.
- **Loading placeholders.** While the dashboard loads it shows a shimmering outline of the page, and the vehicle picture fades in once it has loaded.

## [1.4.1] - 2026-10-18

### Changed

- The HACS check now runs every validation, including the brand icon, so the integration can be listed in the HACS catalog.

## [1.4.0] - 2026-10-10

### Changed

- **Linked to your Ford vehicle.** On Home Assistant 2026.8 and later, Ford Assistant has its own device, named after your vehicle, that shows up under **Linked devices** on the Ford integration's vehicle page, and the vehicle shows up under Linked devices on Ford Assistant's. Existing installs keep their entities and entity IDs; the device Home Assistant already split off for Ford Assistant is reused. On earlier versions nothing changes: the entities stay on the Ford vehicle's device.

### Fixed

- On Home Assistant 2026.8 and later, finding the Ford vehicle could pick Ford Assistant's own device instead, so notification taps and the vehicle name could point at the wrong device.
- Removed device registry calls that Home Assistant 2026.10 deprecates (`async_get_device`, indexing `devices` and `config_entries`), which logged warnings and would stop working in 2027.

## [1.3.1] - 2026-10-08

### Fixed

- Open-door lists in the status Live Activity, the door open alert and the night lock message included the doors sensor's own "Icon" and "Friendly_name" attributes. Only actual doors are listed now.
- A door reported open just as you park is now double-checked. Ford often reports the driver's door ajar in the update sent as the ignition turns off and doesn't report again once it's closed. If a door still looks open two minutes after parking, Ford Assistant asks the vehicle for a fresh status (once), which clears a stale reading well before the door open alert would go out. This uses the Ford integration's **Request refresh** button, if it's enabled.

## [1.3.0] - 2026-10-08

### Added

- **Vehicle status Live Activity.** An optional Live Activity (Live Update on Android) that stays on your lock screen showing the vehicle's lock state, open doors and windows, fuel or battery with range, charging, where it is and the outside temperature, with a fuel or battery progress bar. It turns red when something needs attention, shows the remote start countdown while it's running, updates only when something visible changes, and restarts itself before iOS's 8-hour limit. Turn it on with the new **Vehicle status Live Activity** switch.

### Fixed

- The README said the remote start Live Activity has Stop and Extend buttons on iOS. iOS doesn't support buttons in Live Activities; they work on Android.

## [1.2.0] - 2026-10-07

### Added

- **Remote start Live Activity.** While remote start is running, your phone shows a Live Activity (Live Update on Android) that counts down the time left, with **Stop** and **Extend** buttons. It updates when the time is extended and goes away when remote start stops or you get in. Morning pre-conditioning uses it instead of a separate notification.
- **Quiet hours.** Hold non-urgent alerts (fuel, oil, 12V battery, tires, warning lights, windows) between set times and deliver them when quiet hours end. Anything that resolves overnight is dropped. The alarm and door alerts always go through. Off by default.
- **Electric and plug-in hybrid support.** For vehicles with a high-voltage battery: a plug-in reminder at a set time when the battery is below a level and the vehicle is home and unplugged, alerts when charging finishes or stops because of a fault, and battery level in place of fuel for low-energy alerts and remote start checks. These entities only appear for electric and plug-in hybrid vehicles.
- **Copy settings from the blueprint.** Setup finds a FordPass – Vehicle Assistant blueprint automation for the vehicle, copies its phones, places, days, feature toggles, thresholds and times, and can turn the automation off for you.
- Tapping a notification opens the vehicle's device page.

## [1.1.0] - 2026-10-07

### Added

- **Lock at night.** At a set time (10 PM by default), locks the vehicle if it's still unlocked with the ignition off, wherever it's parked. If a door or the hood is open it sends a time-sensitive notification saying which one instead.
- **Door open alert.** Notifies when a door or the hood has been open for a while (10 minutes by default) with the ignition off, naming which ones. It's sent as time-sensitive, so it gets through Focus and Do Not Disturb (high priority on Android) without a critical siren.
- **Clear resolved notifications.** Alerts are removed from your phones once the problem clears: windows or doors closed, fuel, oil or 12V battery back up, tire pressure or warning lights back to normal, the alarm back to a normal state, or remote start stopped. Getting back in the vehicle also clears the start, lock and garage notifications. Turn it off with the new switch if you'd rather keep them.

## [1.0.0] - 2026-10-06

### Added

- First release, ported from the FordPass – Vehicle Assistant blueprint.
- Config flow that finds a Ford integration vehicle and its entities by unique ID; options for notify phones, zones, weather, to-do list, garage door, schedule days and normal alarm states.
- Auto-lock away from home with optional walk-away distance, morning pre-conditioning, leaving-work start prompt and auto-extend remote start.
- Alerts for alarm, windows open with rain coming, low fuel, oil change, 12V battery, tire pressure and warning lights. Alerts fire once and re-arm after the condition clears.
- Garage door open on arrival and close after parking.
- Actionable notifications with Lock, Honk & Flash, Start and Stop buttons.
- Feature switches, number and time settings on the vehicle's device, a last-event sensor, a `ford_assistant_alert` event, a repair issue for missing Ford entities, and diagnostics.

[1.8.0]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.7.2...v1.8.0
[1.7.2]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.7.1...v1.7.2
[1.7.1]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.6.4...v1.7.0
[1.6.4]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.6.3...v1.6.4
[1.6.3]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.6.2...v1.6.3
[1.6.2]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.6.1...v1.6.2
[1.6.1]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/bisman-automations/ha-ford-assistant/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/bisman-automations/ha-ford-assistant/releases/tag/v1.0.0
