# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-10-07

### Added

- **Lock at night.** At a set time (10 PM by default), locks the vehicle if it's still unlocked with the ignition off, wherever it's parked. If a door or the hood is open it tells you which one instead.
- **Door open alert.** Notifies when a door or the hood has been open for a while (10 minutes by default) with the ignition off, naming which ones.
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
