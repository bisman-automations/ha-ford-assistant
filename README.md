<p align="center">
  <img src="custom_components/ford_assistant/brand/icon@2x.png" alt="Ford Assistant" width="160">
</p>

# Ford Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/bisman-automations/ha-ford-assistant/actions/workflows/validate.yaml/badge.svg)](https://github.com/bisman-automations/ha-ford-assistant/actions/workflows/validate.yaml)

A companion to the [Ford integration](https://github.com/marq24/ha-fordpass) for Home Assistant. It turns your Ford or Lincoln's entities into ready-to-use features, each one a switch you can flip from a dashboard or your own automations.

- **Auto-lock away from home.** Locks the doors if they're left unlocked with the ignition off and doors closed, optionally waiting until your phone has walked away.
- **Lock at night.** Locks it at bedtime wherever it's parked, or tells you which door is open.
- **Morning pre-conditioning.** Remote starts at a set time on chosen days when it's colder or hotter than your limits and there's enough fuel.
- **Leaving-work start prompt.** A notification with a **Start** button at the end of your workday.
- **Auto-extend remote start.** Presses Extend when the remote start timer runs low.
- **Remote start Live Activity.** A countdown on your lock screen while remote start runs, with Stop and Extend buttons.
- **Alerts.** Alarm (critical), windows open with rain coming, low fuel, oil change (adds a to-do item), 12V battery, tire pressure, and dashboard warning lights. Each alert fires once, re-arms only after the problem clears, and is removed from your phone when it's resolved.
- **Door open alert.** Tells you which door or the hood has been left open, as a time-sensitive notification that gets through Focus.
- **Garage door.** Opens when the vehicle arrives home and closes a while after you park.
- **Quiet hours.** Holds non-urgent alerts overnight and delivers them in the morning; the alarm and door alerts always get through.
- **Electric and plug-in hybrid support.** Plug-in reminders, charging finished and charging fault alerts, and battery level in place of fuel.
- **Actionable notifications.** **Lock**, **Honk & Flash**, **Start** and **Stop** buttons right in the notification.

> Ford Assistant is unofficial and not affiliated with Ford Motor Company.

## Requirements

- Home Assistant 2026.2 or newer.
- The [Ford integration](https://github.com/marq24/ha-fordpass) set up with your vehicle.
- The Home Assistant Companion app on the phones that should get notifications.

## Installation

### HACS

1. In HACS, open the menu → **Custom repositories**.
2. Add `https://github.com/bisman-automations/ha-ford-assistant` as an **Integration**.
3. Install **Ford Assistant** and restart Home Assistant.

### Manual

Copy `custom_components/ford_assistant` into your `config/custom_components` folder and restart.

## Setup

1. Go to **Settings → Devices & services → Add integration → Ford Assistant**.
2. Pick your vehicle. Ford Assistant finds its lock, tracker, sensors, remote start switch and buttons on its own, even if you've renamed them.
3. If you used the **FordPass – Vehicle Assistant** blueprint, Ford Assistant offers to copy its settings and turn the automation off.
4. Choose the phones to notify and your home zone. Work zone, weather, to-do list and garage door are optional, and every feature that needs one simply stays idle without it.

Add Ford Assistant once per vehicle. Change notify targets, zones, and the days for pre-conditioning and the work prompt any time under **Configure**.

## Entities

Ford Assistant's entities appear on your vehicle's existing device page, next to the Ford integration's own.

| Type | Entities |
| --- | --- |
| Switch | One per feature: auto-lock, lock at night, pre-conditioning, work prompt, auto-extend, the remote start Live Activity, each alert, garage open and garage close, clearing resolved notifications, and quiet hours. Electric and plug-in hybrid vehicles also get plug-in reminder and charging alert switches. |
| Number | Auto-lock delay, walk-away distance, cold and hot start limits, minimum fuel to start, extend threshold, fuel / oil / 12V battery thresholds, door open alert delay, garage close delay, and (electric/plug-in hybrid) the plug-in reminder battery level |
| Time | Pre-conditioning time, leaving-work prompt time, night lock time, quiet hours start and end, and (electric/plug-in hybrid) plug-in reminder time |
| Sensor | Last event: the most recent alert or action, with its message and time |

Temperature limits use the units of the vehicle's outdoor temperature sensor. The walk-away distance uses your Home Assistant unit system (miles or kilometers).

## Events

Every alert and action also fires a `ford_assistant_alert` event, so you can route alerts your own way (TTS, a smart display, a different notify service):

```yaml
triggers:
  - trigger: event
    event_type: ford_assistant_alert
    event_data:
      type: windows
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.kitchen
      message: "{{ trigger.event.data.message }}"
```

Event data: `vin`, `config_entry_id`, `type`, `title`, `message`. Types: `autolock`, `nightlock`, `door`, `start`, `plugin`, `charge`, `extend`, `alarm`, `windows`, `fuel`, `oil`, `battery`, `tires`, `indicators`, `garage_open`, `garage`, and `command_lock` / `command_honk` / `command_start` / `command_stop` / `command_extend` for notification buttons.

## Coming from the blueprint

When you add Ford Assistant, it looks for a **FordPass – Vehicle Assistant** blueprint automation that controls the same vehicle. Pick it to copy its phones, places, days, feature toggles, thresholds and times, and leave **Turn off the blueprint automation** checked so you don't get every notification twice. The automation is only turned off, not deleted.

## Live Activity

While remote start is running, Ford Assistant sends a Live Activity (iOS) or Live Update (Android) through the Companion app, counting down the time left with **Stop** and **Extend** buttons. Your phone counts down by itself, so it's only updated when the time jumps, like after an extend. Turn it off with the **Remote start Live Activity** switch to get a regular "warming up" notification instead.

## Diagnostics

**Settings → Devices & services → Ford Assistant → ⋮ → Download diagnostics** includes the matched Ford entities and their states, with the VIN and locations redacted.
