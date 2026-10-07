# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
