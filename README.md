<p align="center">
  <img src="https://raw.githubusercontent.com/bisman-automations/ha-ford-assistant/main/custom_components/ford_assistant/brand/icon.png" alt="Ford Assistant icon" width="128">
</p>

# Ford Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-blue.svg)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/bisman-automations/ha-ford-assistant)](https://github.com/bisman-automations/ha-ford-assistant/releases)
[![Test](https://github.com/bisman-automations/ha-ford-assistant/actions/workflows/test.yml/badge.svg)](https://github.com/bisman-automations/ha-ford-assistant/actions/workflows/test.yml)
[![Validate](https://github.com/bisman-automations/ha-ford-assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/bisman-automations/ha-ford-assistant/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/bisman-automations/ha-ford-assistant)](LICENSE)

A companion to the [Ford integration](https://github.com/marq24/ha-fordpass) for Home Assistant. It turns your Ford or Lincoln's entities into ready-to-use features, each one a switch you can flip from a dashboard or your own automations.

It also works with [FordPass China](https://github.com/RockJesus/ha-fordpass-cn): pick the car from either integration during setup, and everything below — alerts, dashboard, Live Activities and Who's driving — runs on the readings that integration provides.

- **Sidebar dashboard.** A Ford Assistant page in the sidebar with your vehicle's picture, its status at a glance, one-tap controls and every Ford Assistant feature switch.
- **Auto-lock away from home.** Locks the doors if they're left unlocked with the ignition off and doors closed, optionally waiting until your phone has walked away.
- **Lock at night.** Locks it at bedtime wherever it's parked, or tells you which door is open.
- **Morning pre-conditioning.** Remote starts at a set time on chosen days when it's colder or hotter than your limits and there's enough fuel.
- **Leaving-work start prompt.** A notification with a **Start** button at the end of your workday.
- **Auto-extend remote start.** Presses Extend when the remote start timer runs low.
- **Remote start Live Activity.** A countdown on your lock screen while remote start runs.
- **Vehicle status Live Activity.** Optional: your vehicle's lock state, doors, fuel or battery, location and temperature, always on your lock screen.
- **Alerts.** Alarm (critical), windows open with rain coming, low fuel, oil change (adds a to-do item), 12V battery, tire pressure, and dashboard warning lights. Each alert fires once, re-arms only after the problem clears, and is removed from your phone when it's resolved.
- **Door open alert.** Tells you which door or the hood has been left open, as a time-sensitive notification that gets through Focus.
- **Garage door.** Opens when the vehicle arrives home and closes a while after you park. It only opens for an arrival reported while you're still driving: not when Home Assistant or Ford Assistant has just started, not when the vehicle is already parked by the time its location catches up, and not when the door was opened or closed in the last 10 minutes. Each time Ford Assistant opens or closes the door, the garage door's **Activity** says Ford Assistant did it and why.
- **Quiet hours.** Holds non-urgent alerts overnight and delivers them in the morning; the alarm and door alerts always get through.
- **Electric and plug-in hybrid support.** Plug-in reminders, charging finished and charging fault alerts, and battery level in place of fuel.
- **Who's driving.** Household, Service or Guest, so a workshop visit or a borrowed car doesn't auto-lock, remote-start or open the garage. Household drivers each have their own alerts, phones and actions.
- **Actionable notifications.** **Lock**, **Honk & Flash**, **Start** and **Stop** buttons right in the notification.

> Ford Assistant is unofficial and not affiliated with Ford Motor Company.

## Requirements

- Home Assistant 2026.8 or newer.
- The [Ford integration](https://github.com/marq24/ha-fordpass) or [FordPass China](https://github.com/RockJesus/ha-fordpass-cn) set up with your vehicle.
- The Home Assistant Companion app on the phones that should get notifications.

## FordPass China

FordPass China splits the car over many entities and reports them in Chinese; it also has no lock entity, using separate lock and unlock action buttons instead. Ford Assistant adds a few **bridge entities** to a FordPass China vehicle so the rest of the integration sees the shapes it was built for:

| Bridge entity | Built from |
| --- | --- |
| Vehicle lock | Lock status sensor, lock and unlock action buttons |
| Doors | Driver, passenger and rear door sensors, tailgate, hood |
| Windows | The four window sensors and the sunroof |
| Tire pressure | The four tire pressure and tire status sensors |
| Alarm | Alarm status sensor |
| Ignition, Remote start | Ignition sensor, engine switch |
| Fuel, Battery | Fuel level and electric range, charge level and range |
| Charging plug, Charging | Plug status and charging status sensors |
| Honk and flash | Honk switch |

Refresh, location, odometer, oil life, the remote-start countdown and the vehicle picture come straight from the FordPass China entities.

FordPass China has no 12V battery percentage, outside temperature or dashboard warning-light count, so the 12V battery alert, the temperature check in morning pre-conditioning and the warning-light alert stay out. Everything else works as it does with the Ford integration.

## Installation

Requires **Home Assistant 2026.8 or newer**.

### Marketplace (Home Assistant 2026.11 and newer, recommended)

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=bisman-automations&repository=ha-ford-assistant&category=integration)

1. Open the Marketplace and search for **Ford Assistant**, or select the button above to open this repository in the Marketplace.
2. Download **Ford Assistant** and restart Home Assistant.

New versions show up under **Settings > Updates**. Already installed Ford Assistant with
HACS? There's nothing to do: Home Assistant moves it into the Marketplace the
first time it starts on 2026.11.

### HACS (Home Assistant 2026.10 and older)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bisman-automations&repository=ha-ford-assistant&category=integration)

1. Open HACS and search for **Ford Assistant**, or select the button above to open this repository in HACS.
2. Download **Ford Assistant** and restart Home Assistant.

### Custom repository

If **Ford Assistant** does not appear in search:

1. In HACS open the menu, choose **Custom repositories**, and add `https://github.com/bisman-automations/ha-ford-assistant` as an **Integration**.
2. Download **Ford Assistant** and restart Home Assistant.

### Manual

Download `ford_assistant.zip` from the [latest release](https://github.com/bisman-automations/ha-ford-assistant/releases/latest), unzip it into `config/custom_components/ford_assistant/`, and restart Home Assistant.

## Setup

[![Open your Home Assistant instance and start setting up Ford Assistant.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ford_assistant)

1. Go to **Settings → Devices & services → Add integration → Ford Assistant**.
2. Pick your vehicle. Ford Assistant finds its lock, tracker, sensors, remote start switch and buttons on its own, even if you've renamed them.
3. If you used the **FordPass – Vehicle Assistant** blueprint, Ford Assistant offers to copy its settings and turn the automation off.
4. Choose the phones to notify and your home zone. Work zone, weather, to-do list and garage door are optional, and every feature that needs one simply stays idle without it.

Add Ford Assistant once per vehicle. Change notify targets, zones, and the days for pre-conditioning and the work prompt any time under **Configure**.

## Entities

On Home Assistant 2026.8 and later, Ford Assistant has its own device named after your vehicle, shown under **Linked devices** on the Ford integration's vehicle page (and the other way around), so you can jump between them. On earlier versions its entities appear directly on the Ford integration's vehicle device.

| Type | Entities |
| --- | --- |
| Switch | One per feature: auto-lock, lock at night, pre-conditioning, work prompt, auto-extend, the remote start and vehicle status Live Activities, each alert, garage open and garage close, clearing resolved notifications, and quiet hours. Electric and plug-in hybrid vehicles also get plug-in reminder and charging alert switches. |
| Number | Auto-lock delay, walk-away distance, cold and hot start limits, minimum fuel to start, extend threshold, fuel / oil / 12V battery thresholds, door open alert delay, garage close delay, and (electric/plug-in hybrid) the plug-in reminder battery level |
| Time | Pre-conditioning time, leaving-work prompt time, night lock time, quiet hours start and end, and (electric/plug-in hybrid) plug-in reminder time |
| Select | **Who's driving** (Household, Service or Guest) and **Active driver** (a household person, or Nobody) |
| Sensor | Last event: the most recent alert or action, with its message and time. Driving status: the current mode, with the active driver and the actions and alerts that are allowed or blocked |
| Binary sensor | **Automations suppressed**, on while the current mode blocks at least one action |

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

Changing who's driving fires `ford_assistant_driving_mode_changed`. Event data: `vin`, `config_entry_id`, `mode`, `previous_mode`, `active_driver`, `previous_driver`, `reason` (`manual`, `service`, `detected`, `parked`, `revert` or `duration`), `allowed_actions`, `blocked_actions`, `kept_alerts`, `dropped_alerts`, `automations_suppressed`, `revert_at`. The same event fires when the active driver changes.

```yaml
triggers:
  - trigger: event
    event_type: ford_assistant_driving_mode_changed
    event_data:
      mode: service
actions:
  - action: notify.persistent_notification
    data:
      title: The car is in for service
      message: Ford Assistant won't lock, start or open the garage until it's back.
```

## Who's driving

**Who's driving** is a list on the vehicle: **Household**, **Service** or **Guest**. It stays where you set it across restarts. The feature switches are not changed. The mode only decides which of them Ford Assistant actually runs, so switching back puts everything the way it was.

The dashboard shows the mode, and disables a button the mode blocks. **Refresh** always works. Calling the Ford integration's own lock or start from somewhere else still works; those entities belong to the Ford integration. Ford Assistant won't start a blocked action itself, including from a notification button or a Live Activity button.

**Automations suppressed** is on while at least one action is blocked. **Driving status** (and the attributes on **Who's driving**) list the mode, the active driver, `allowed_actions`, `blocked_actions`, `kept_alerts` and `dropped_alerts`, and when the mode will return to Household.

### Household

Under **Settings → Devices & services → Ford Assistant → Configure → Household drivers**, pick the Home Assistant people who drive this vehicle. Each person then has a profile:

- **Alerts they receive.** Unchecked alerts are skipped while they are the active driver.
- **Their phones.** Leave this empty to use the phones chosen for the vehicle. Otherwise alerts for this driver go only to these phones.
- **Actions enabled for them.** Unchecked actions don't run, even if the feature switch is on.

**Active driver** lists those people, plus **Nobody**. With nobody selected, every feature follows its own switch.

Ford Assistant fills **Active driver** when it can:

- You can always choose someone yourself. That choice stays until the vehicle is parked at home.
- When the vehicle leaves home (its location leaves the home zone, or the ignition turns on while it's already away), Ford Assistant looks at the household people. A person counts if they, or one of their device trackers, changed from home to away within 15 minutes of the vehicle leaving.
- Exactly one such person becomes the active driver. If nobody left, or more than one person did, Ford Assistant doesn't guess.
- Someone who was already away when Ford Assistant started is not assumed to be driving. Only a leave-home it sees counts.
- Parking at home (the vehicle is in the home zone and the ignition is off) clears the driver, so the next trip can be detected. This is skipped for the first 3 minutes after Home Assistant or Ford Assistant starts, so a restart doesn't forget a trip that's already underway.

The Ford integration does not publish a phone-as-a-key entity (nothing in its data names a person or a phone), so Ford Assistant uses the device tracker already attached to the person's profile in Home Assistant.

A household driver can open the Ford Assistant page when their person is linked to their Home Assistant user (**Settings → People**). A person with no user can still be the active driver; they just can't open the page. Until you pick any household drivers, dashboard access is unchanged.

### Service

Use **Service** while the car is being worked on. By default every alert still goes out, and every action is blocked: auto-lock, lock at night, lock, unlock, honk, morning pre-conditioning, the leaving-work prompt, auto-extend, remote start, and both garage actions. Asking the vehicle for a fresh status is never blocked.

Change the two checklists under **Configure → Service mode**. **Return to Household after** is optional. Leave it empty to stay in Service until someone changes it. The countdown survives a restart.

### Guest

Use **Guest** when someone else has the car. By default:

- **Kept:** alarm, windows open in the rain, low fuel, 12V battery, tire pressure, warning lights, a door left open, charging, and the vehicle status Live Activity.
- **Dropped:** oil life, the plug-in reminder, and the remote start Live Activity.
- **Allowed:** auto-lock, lock, unlock, and honk and flash.
- **Blocked:** lock at night, morning pre-conditioning, the leaving-work prompt, auto-extend, remote start, and both garage actions.

**Configure → Guest mode** has the same checklists and the same optional return to Household.

### Set it from an automation

```yaml
action: ford_assistant.set_driving_mode
target:
  entity_id: select.your_vehicle_whos_driving
data:
  mode: service
  duration:
    hours: 4
```

`mode` is `household`, `service` or `guest`. Leave `duration` out to use the one from **Configure**. Set it to `0` to stay until someone changes the mode. `active_driver` is optional and must be one of the household drivers (or `none`). Choosing a driver this way is a manual choice until the vehicle is parked at home.

An alert that was held back is sent when you return to a mode that keeps it, if the problem is still there. Ford Assistant doesn't repeat an alert that's already on your phone.

## Coming from the blueprint

When you add Ford Assistant, it looks for a **FordPass – Vehicle Assistant** blueprint automation that controls the same vehicle. Pick it to copy its phones, places, days, feature toggles, thresholds and times, and leave **Turn off the blueprint automation** checked so you don't get every notification twice. The automation is only turned off, not deleted.

## Dashboard

Ford Assistant adds a **Ford Assistant** page to the Home Assistant sidebar as soon as a vehicle is set up. There's nothing to configure.

- **Your vehicle** front and center, using the picture from the Ford integration (recent versions; older ones show a placeholder), with a status chip: Locked, Unlocked, Locking…, Unlocking…, Lock jammed, Door open, Running, Driving or Alarm. After you tap **Lock** or **Unlock** it says **Locking…** or **Unlocking…** until the vehicle confirms it (up to 90 seconds).
- **Controls**: Lock or Unlock, remote Start or Stop (and Extend while running), Honk & Flash, the garage door if you've set one, and Refresh. Unlock, Start and opening the garage ask you to confirm first. A button shows "Sending…" until the vehicle reports back, since Ford commands can take a while.
- **Status tiles**: fuel or battery with range, charging, remote start time left, doors, windows, location, tire pressures, oil life, 12V battery, alarm, warning lights, outside temperature and odometer. Tiles turn amber or red when something needs attention, and tapping one opens its details.
- **Ford Assistant features**, grouped by Security, Remote start, Alerts, Garage and Notifications, each with an on/off switch, plus a shortcut to the thresholds and times.
- With more than one vehicle, a tab for each.

### Who can use it

Admins always can. So can a household driver whose person is linked to their Home Assistant user, and anyone an admin checks under **Who can use Ford Assistant** at the bottom of the dashboard. The same people can change Ford Assistant's own switches, thresholds, times and who's driving; automations always can. The Ford integration's own entities keep Home Assistant's usual permissions.

Home Assistant can't show a sidebar entry to only some people, so once anyone who isn't an admin is checked, everyone sees Ford Assistant in the sidebar, and people who aren't checked get a page saying they don't have access.

While it loads, the page shows a placeholder layout so it doesn't jump around, and the vehicle picture fades in once it's ready. To hide the page, long-press the sidebar title and remove it there.

## Live Activities

Live Activities need the Home Assistant Companion app on iOS 17.2 or later (Live Updates on Android 16 or later) and Home Assistant 2026.7 or later. Tapping one opens the vehicle's device page.

### Remote start

While remote start is running, Ford Assistant shows a Live Activity counting down the time left. Your phone counts down by itself, so it's only updated when the time jumps, like after an extend. On Android it also has **Stop** and **Extend** buttons; iOS doesn't support buttons in Live Activities. Turn it off with the **Remote start Live Activity** switch to get a regular "warming up" notification instead.

### Vehicle status

Turn on **Vehicle status Live Activity** to keep your vehicle's status on the lock screen at all times:

- **Headline** (Dynamic Island and status bar): Locked, Unlocked, Door open, Running, Driving or Alarm.
- **Details**: open doors and windows, lock state, fuel or battery with range, charging, home or the zone it's in, and outside temperature.
- **Progress bar**: fuel or battery level.
- It turns red when something needs attention: unlocked or windows open away from home, a door open, or the alarm going off.
- While remote start runs, it shows the countdown, so you don't get a second activity.
- On Android it has **Lock** and **Start**/**Stop** buttons.

To be easy on your phone, it only updates when something you'd see changes. Lock, door, remote start and alarm changes show right away; small fuel, temperature or location changes go out quietly at most every 5 minutes. iOS ends any Live Activity after 8 hours, so Ford Assistant quietly restarts it before then.

## Languages

Ford Assistant is in English and French.

- **Setup, settings and the dashboard** follow each person's own language in Home Assistant (their profile).
- **Notifications and Live Activities** follow Home Assistant's language (**Settings → System → General**), since they go to phones rather than to one person's screen.
- Readings Ford Assistant doesn't know a word for (an unusual warning light, say) are spelled out in English.

To add a language, translate `translations/en.json` into `translations/<language>.json`, the `en` block in `messages.py` (notifications), and the `en` block of `WORDS` in `frontend/ford-assistant-panel.js` (dashboard), keeping every `{placeholder}`.

## Diagnostics

**Settings → Devices & services → Ford Assistant → ⋮ → Download diagnostics** includes the matched Ford entities and their states, with the VIN and locations redacted.
## Troubleshooting

### Diagnostics and debug logs

When something goes wrong, download diagnostics from **Settings → Devices & services → Ford Assistant → ⋮ → Download diagnostics** and check the file before you share it.

For debug logs, use **Enable debug logging** on the integration page, or add this to `configuration.yaml` and restart:

```yaml
logger:
  logs:
    custom_components.ford_assistant: debug
```

Then open an [issue](https://github.com/bisman-automations/ha-ford-assistant/issues/new/choose) with the diagnostics, the log, and your Home Assistant and Ford Assistant versions.

## Development

Tests run inside a real Home Assistant through
[pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component).
You need Python 3.14 for the current Home Assistant.

```bash
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

To test against the oldest supported Home Assistant (2026.8), use Python 3.14 and
`pip install -r requirements_test_min.txt` instead.

CI runs the same checks on every push and pull request, on both Home Assistant
versions, plus hassfest, HACS validation and the shared repo standards, using the
workflows in [bisman-automations/.github](https://github.com/bisman-automations/.github).
Releases are drafted from [CHANGELOG.md](CHANGELOG.md); see [CLAUDE.md](CLAUDE.md).

## License

MIT. See [LICENSE](LICENSE).
