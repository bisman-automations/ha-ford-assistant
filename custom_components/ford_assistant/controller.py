"""Runtime logic for one vehicle."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
import logging
from typing import Any

from homeassistant.components.zone import in_zone
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfLength,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import (
    async_call_later,
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance as gps_distance

from .const import (
    ACTIVITY_COLOR,
    CHARGE_DONE,
    CHARGE_FAULTS,
    CHARGE_IN_PROGRESS,
    CONF_ALARM_NORMAL_STATES,
    CONF_GARAGE,
    CONF_HOME_ZONE,
    CONF_NOTIFY_DEVICES,
    CONF_PHONE_TRACKER,
    CONF_PRECONDITION_DAYS,
    CONF_TODO,
    CONF_VIN,
    CONF_WEATHER,
    CONF_WORK_PROMPT_DAYS,
    CONF_WORK_ZONE,
    DEFAULT_ALARM_NORMAL_STATES,
    DEFAULT_DAYS,
    DOMAIN,
    DOOR_RECHECK_DELAY,
    EV_ROLES,
    EVENT_ALERT,
    FEATURES,
    NOTIFICATION_ACTION_EVENT,
    NUMBERS,
    PLUG_DISCONNECTED,
    STORAGE_VERSION,
    TIMES,
    WEEKDAYS,
    WINDOW_OPEN_DELAY,
)
from .discovery import ford_device, resolve_entities, vehicle_name
from .status import StatusActivity
from .logic import (
    action_id,
    active_indicators,
    countdown_minutes,
    in_quiet_hours,
    notify_service_name,
    open_doors,
    parse_action,
    percent_alert,
    rain_expected,
    state_alert,
    temp_wants_start,
    tire_summary,
    to_float,
)

_LOGGER = logging.getLogger(__name__)

BAD_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE, None)
EXTEND_COOLDOWN = 60  # seconds between extend presses


class FordAssistantController:
    """Watches one vehicle's Ford entities and acts on them."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the controller."""
        self.hass = hass
        self.entry = entry
        self.vin: str = entry.data[CONF_VIN]
        self.entities: dict[str, str] = {}
        self.features: dict[str, bool] = dict(FEATURES)
        self.numbers: dict[str, float] = {k: s.default for k, s in NUMBERS.items()}
        self.times: dict[str, time] = {k: time.fromisoformat(v) for k, v in TIMES.items()}
        self.latched: dict[str, bool] = {}
        # Notification kinds currently showing on phones (cleared when resolved).
        self.shown: set[str] = set()
        self.last_event: dict[str, Any] | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._time_unsubs: dict[str, CALLBACK_TYPE] = {}
        self._last_countdown: float | None = None
        self._last_extend: datetime | None = None
        # Alerts held during quiet hours: kind -> notify payload.
        self._deferred: dict[str, dict[str, Any]] = {}
        # Remote start Live Activity
        self._activity_active = False
        self._activity_sent_minutes: float | None = None
        self._activity_sent_at: datetime | None = None
        self._activity_pending = False
        self._door_rechecked = False
        # Always-on vehicle status Live Activity
        self.status = StatusActivity(self)

    # ------------------------------------------------------------------ setup

    @property
    def name(self) -> str:
        """Vehicle display name."""
        return vehicle_name(ford_device(self.hass, self.vin), self.vin)

    @property
    def options(self) -> dict[str, Any]:
        """Merged entry data and options."""
        return {**self.entry.data, **self.entry.options}

    async def async_load(self) -> None:
        """Restore saved settings and resolve the Ford entities."""
        if stored := await self._store.async_load():
            for key, value in stored.get("features", {}).items():
                if key in self.features:
                    self.features[key] = bool(value)
            for key, value in stored.get("numbers", {}).items():
                if key in self.numbers and (number := to_float(value)) is not None:
                    self.numbers[key] = number
            for key, value in stored.get("times", {}).items():
                if key in self.times:
                    try:
                        self.times[key] = time.fromisoformat(value)
                    except (TypeError, ValueError):
                        pass
            self.latched = {k: bool(v) for k, v in stored.get("latched", {}).items()}
            self.shown = set(stored.get("shown", []))
            self._deferred = dict(stored.get("deferred", {}))
            if started := stored.get("status_started"):
                self.status.started_at = dt_util.parse_datetime(started)
        elif imported := self.entry.data.get("imported"):
            # First start after importing a blueprint automation's settings.
            for key, value in imported.get("features", {}).items():
                if key in self.features:
                    self.features[key] = bool(value)
            for key, value in imported.get("numbers", {}).items():
                if key in self.numbers and (number := to_float(value)) is not None:
                    self.numbers[key] = number
            for key, value in imported.get("times", {}).items():
                if key in self.times:
                    try:
                        self.times[key] = time.fromisoformat(value)
                    except (TypeError, ValueError):
                        pass
            self._save()
        self.entities = resolve_entities(self.hass, self.vin)

    @property
    def is_electric(self) -> bool:
        """Electric or plug-in hybrid (the Ford integration made EV sensors)."""
        return any(role in self.entities for role in EV_ROLES)

    @callback
    def async_start(self) -> None:
        """Subscribe to everything."""
        e = self.entities
        watch = {
            "lock": self._on_lock,
            "ignition": self._on_ignition,
            "doors": self._on_doors,
            "windows": self._on_windows,
            "countdown": self._on_countdown,
            "alarm": self._on_alarm,
            "fuel": self._on_fuel,
            "oil": self._on_oil,
            "battery": self._on_battery,
            "tires": self._on_tires,
            "indicators": self._on_indicators,
            "tracker": self._on_tracker,
            "remote_start": self._on_remote_start,
            "soc": self._on_fuel,
            "ev_plug": self._on_plug,
            "ev_charging": self._on_charging,
        }
        for role, handler in watch.items():
            if role in e:
                self._unsubs.append(
                    async_track_state_change_event(self.hass, e[role], handler)
                )

        self._unsubs.append(
            self.hass.bus.async_listen(NOTIFICATION_ACTION_EVENT, self._on_action)
        )
        self._unsubs.append(
            async_track_time_change(self.hass, self._on_hourly, minute=0, second=0)
        )
        # Reload if someone renames one of the Ford entities we watch.
        self._unsubs.append(
            async_track_entity_registry_updated_event(
                self.hass, list(e.values()), self._on_registry_update
            )
        )
        for key in self.times:
            self._schedule_time(key)

        # Pick up conditions that were already true at startup.
        if self._is(e.get("lock"), "unlocked") or self._ignition_off():
            self._start_timer("auto_lock", self._auto_lock_delay, self._check_auto_lock)
        if self._windows_open():
            self._start_timer("windows", WINDOW_OPEN_DELAY, self._check_windows)
        if self._doors_open() and self._ignition_off():
            self._start_timer("door_open", self._door_open_delay, self._check_door_open)
            self._schedule_door_recheck()
        if self._deferred and not self._quiet_now():
            self.hass.async_create_task(self._flush_deferred())
        if self._is(e.get("remote_start"), "on"):
            self._schedule_activity_update()
        self.status.async_start()

    @callback
    def async_stop(self) -> None:
        """Tear everything down."""
        self.status.async_stop()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for unsub in [*self._timers.values(), *self._time_unsubs.values()]:
            unsub()
        self._timers.clear()
        self._time_unsubs.clear()

    # ------------------------------------------------------- settings / state

    @callback
    def async_add_listener(self, update: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Register an entity update callback."""
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def _notify_listeners(self) -> None:
        for update in list(self._listeners):
            update()

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(self._data_to_save, 1)

    async def async_flush(self) -> None:
        """Write settings now (used on unload so a reload sees them)."""
        await self._store.async_save(self._data_to_save())

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "features": self.features,
            "numbers": self.numbers,
            "times": {k: v.isoformat() for k, v in self.times.items()},
            "latched": self.latched,
            "shown": sorted(self.shown),
            "deferred": self._deferred,
            "status_started": self.status.started_at.isoformat()
            if self.status.started_at
            else None,
        }

    @callback
    def set_feature(self, key: str, value: bool) -> None:
        """Turn a feature on or off."""
        self.features[key] = value
        if not value:
            self._cancel_timer(key)
        if key == "quiet_hours" and not value and self._deferred:
            self.hass.async_create_task(self._flush_deferred())
        if key == "remote_start_activity" and not value and self._activity_active:
            self.hass.async_create_task(self._activity_end())
        if key == "status_activity":
            if value:
                # The status activity shows remote start itself.
                if self._activity_active:
                    self.hass.async_create_task(self._activity_end())
                self.hass.async_create_task(self.status.async_turned_on())
            else:
                self.hass.async_create_task(self.status.async_turned_off())
        self._save()
        self._notify_listeners()

    @callback
    def set_number(self, key: str, value: float) -> None:
        """Change a number setting."""
        self.numbers[key] = value
        self._save()
        self._notify_listeners()

    @callback
    def set_time(self, key: str, value: time) -> None:
        """Change a time setting."""
        self.times[key] = value
        self._schedule_time(key)
        self._save()
        self._notify_listeners()

    @property
    def _auto_lock_delay(self) -> float:
        return self.numbers["auto_lock_delay"] * 60

    # ---------------------------------------------------------------- helpers

    def _state(self, role: str) -> State | None:
        if (entity_id := self.entities.get(role)) is None:
            return None
        return self.hass.states.get(entity_id)

    def _value(self, role: str) -> str | None:
        state = self._state(role)
        return None if state is None else state.state

    def _number(self, role: str) -> float | None:
        return to_float(self._value(role))

    def _is(self, entity_id: str | None, value: str) -> bool:
        if entity_id is None:
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == value

    def _ignition_off(self) -> bool:
        value = self._value("ignition")
        return value is not None and value.upper() == "OFF"

    def _doors_open(self) -> bool:
        return self._value("doors") == "Open"

    @property
    def _door_open_delay(self) -> float:
        return self.numbers["door_open_delay"] * 60

    def _windows_open(self) -> bool:
        return self._value("windows") not in (*BAD_STATES, "Closed")

    def _in_zone(self, zone_entity_id: str | None, state: State | None = None) -> bool:
        """Whether the vehicle (or a given tracker state) is in a zone."""
        if not zone_entity_id:
            return False
        tracker = state if state is not None else self._state("tracker")
        zone = self.hass.states.get(zone_entity_id)
        if tracker is None or zone is None:
            return False
        lat = tracker.attributes.get(ATTR_LATITUDE)
        lon = tracker.attributes.get(ATTR_LONGITUDE)
        if lat is not None and lon is not None:
            accuracy = to_float(tracker.attributes.get("gps_accuracy")) or 0
            return in_zone(zone, lat, lon, accuracy)
        # No GPS: fall back to the zone name the tracker reports.
        zone_name = "home" if zone_entity_id == "zone.home" else zone.name
        return tracker.state == zone_name

    def _home(self) -> str:
        return self.options.get(CONF_HOME_ZONE) or "zone.home"

    def _today_in(self, conf_key: str) -> bool:
        days = self.options.get(conf_key) or DEFAULT_DAYS
        return WEEKDAYS[dt_util.now().weekday()] in days

    def _energy(self) -> tuple[float | None, str, float | None]:
        """(level %, "fuel" or "battery", range): fuel if the vehicle has it, else the EV battery."""
        for role, source, range_attr in (("fuel", "fuel", "fuelRange"), ("soc", "battery", "batteryRange")):
            if (level := self._number(role)) is not None:
                state = self._state(role)
                return level, source, to_float(state.attributes.get(range_attr)) if state else None
        return None, "fuel", None

    def _fuel_ok_to_start(self) -> bool:
        if "fuel" not in self.entities and "soc" not in self.entities:
            return True
        level, _source, _range = self._energy()
        return level is not None and level >= self.numbers["min_fuel_to_start"]

    def _quiet_now(self) -> bool:
        return self.features["quiet_hours"] and in_quiet_hours(
            dt_util.now().time(), self.times["quiet_start"], self.times["quiet_end"]
        )

    def _tap_url(self) -> str | None:
        """Tapping a notification opens the vehicle's device page."""
        if device := ford_device(self.hass, self.vin):
            return f"/config/devices/device/{device.id}"
        return None

    def _temp_wants_start(self) -> bool:
        return temp_wants_start(
            self._number("temperature"),
            self.numbers["cold_threshold"],
            self.numbers["hot_threshold"],
        )

    def _temp_text(self) -> str:
        temp = self._number("temperature")
        return "" if temp is None else f"It's {round(temp)}° outside. "

    def _start_timer(
        self, key: str, delay: float, action: Callable[[], Any]
    ) -> None:
        self._cancel_timer(key)

        @callback
        def _fire(_now: datetime) -> None:
            self._timers.pop(key, None)
            self.hass.async_create_task(action())

        self._timers[key] = async_call_later(self.hass, delay, _fire)

    def _cancel_timer(self, key: str) -> None:
        if unsub := self._timers.pop(key, None):
            unsub()

    def _schedule_time(self, key: str) -> None:
        if unsub := self._time_unsubs.pop(key, None):
            unsub()
        at = self.times[key]
        handler = {
            "precondition_time": self._precondition,
            "work_prompt_time": self._work_prompt,
            "night_lock_time": self._night_lock,
            "quiet_end": self._flush_deferred,
            "plug_in_time": self._plug_in_reminder,
        }.get(key)
        if handler is None:
            return

        async def _run(_now: datetime) -> None:
            await handler()

        self._time_unsubs[key] = async_track_time_change(
            self.hass, _run, hour=at.hour, minute=at.minute, second=at.second
        )

    def _latch(self, key: str, fire_and_latch: tuple[bool, bool]) -> bool:
        fire, latched = fire_and_latch
        was = self.latched.get(key, False)
        if was != latched:
            self.latched[key] = latched
            self._save()
        if was and not latched:
            # The problem cleared: take the stale alert off the phones.
            self._clear(key)
        return fire

    # ------------------------------------------------------- notifications

    def _notify_services(self) -> list[str]:
        """notify.mobile_app_* services for the chosen phones.

        Read from the mobile_app config entry rather than the device name, so
        renaming the phone's device in HA doesn't break notifications.
        """
        services: list[str] = []
        devices = dr.async_get(self.hass)
        for device_id in self.options.get(CONF_NOTIFY_DEVICES, []):
            device = devices.async_get(device_id)
            if device is None:
                continue
            for entry_id in device.config_entries:
                entry = self.hass.config_entries.async_get_entry(entry_id)
                if entry and entry.domain == "mobile_app" and (
                    name := entry.data.get("device_name")
                ):
                    services.append(notify_service_name(name))
        return services

    async def _notify(
        self,
        kind: str,
        title: str,
        message: str,
        actions: list[str] | None = None,
        critical: bool = False,
        time_sensitive: bool = False,
    ) -> None:
        """Send a notification, fire an event, and record it."""
        data: dict[str, Any] = {"tag": f"ford-{kind}-{self.vin}"}
        if actions:
            data["actions"] = self._actions(actions)
        if critical:
            data["push"] = {"sound": {"name": "default", "critical": 1, "volume": 1.0}}
            data["ttl"] = 0
            data["priority"] = "high"
            data["channel"] = "alarm_stream"
        elif time_sensitive:
            # Breaks through Focus / Do Not Disturb without a critical siren.
            data["push"] = {"interruption-level": "time-sensitive"}
            data["ttl"] = 0
            data["priority"] = "high"
        if url := self._tap_url():
            data["url"] = url
            data["clickAction"] = url

        payload = {"title": title, "message": message, "data": data}
        self._record(kind, title, message)
        if not (critical or time_sensitive) and self._quiet_now():
            # Hold it until quiet hours end; a newer alert of the same kind replaces it.
            self._deferred[kind] = payload
            self._save()
            return
        await self._deliver(payload)
        self.shown.add(kind)
        self._save()

    def _actions(self, commands: list[str]) -> list[dict[str, str]]:
        labels = {
            "LOCK": "Lock",
            "HONK": "Honk & Flash",
            "START": "Start",
            "STOP": "Stop",
            "EXTEND": "Extend",
        }
        return [
            {"action": action_id(cmd, self.vin), "title": labels[cmd]} for cmd in commands
        ]

    async def _deliver(self, payload: dict[str, Any]) -> None:
        for service in self._notify_services():
            if not self.hass.services.has_service("notify", service):
                _LOGGER.warning("Notify service notify.%s not found", service)
                continue
            try:
                await self.hass.services.async_call(
                    "notify", service, payload, blocking=True
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Could not notify via %s: %s", service, err)

    async def _flush_deferred(self) -> None:
        """Send alerts held during quiet hours."""
        if self._quiet_now() or not self._deferred:
            return
        pending, self._deferred = self._deferred, {}
        for kind, payload in pending.items():
            await self._deliver(payload)
            self.shown.add(kind)
        self._save()

    @callback
    def _clear(self, *kinds: str) -> None:
        """Remove resolved notifications from the phones, if any are showing."""
        # Something held for quiet hours that has since resolved is just dropped.
        if any(self._deferred.pop(kind, None) is not None for kind in list(kinds)):
            self._save()
        showing = [kind for kind in kinds if kind in self.shown]
        if not showing:
            return
        self.shown.difference_update(showing)
        self._save()
        if self.features["clear_resolved"]:
            self.hass.async_create_task(self._send_clear(showing))

    async def _send_clear(self, kinds: list[str]) -> None:
        for service in self._notify_services():
            if not self.hass.services.has_service("notify", service):
                continue
            for kind in kinds:
                try:
                    await self.hass.services.async_call(
                        "notify",
                        service,
                        {
                            "message": "clear_notification",
                            "data": {"tag": f"ford-{kind}-{self.vin}"},
                        },
                        blocking=True,
                    )
                except HomeAssistantError as err:
                    _LOGGER.debug("Could not clear %s via %s: %s", kind, service, err)

    @callback
    def _record(self, kind: str, title: str, message: str = "") -> None:
        self.last_event = {
            "type": kind,
            "title": title,
            "message": message,
            "time": dt_util.now(),
        }
        self.hass.bus.async_fire(
            EVENT_ALERT,
            {
                "vin": self.vin,
                "config_entry_id": self.entry.entry_id,
                "type": kind,
                "title": title,
                "message": message,
            },
        )
        self._notify_listeners()

    async def _call(self, domain: str, service: str, role_or_entity: str) -> bool:
        entity_id = self.entities.get(role_or_entity, role_or_entity)
        try:
            await self.hass.services.async_call(
                domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.warning("%s.%s on %s failed: %s", domain, service, entity_id, err)
            return False
        return True

    # ------------------------------------------------------------ auto-lock

    @callback
    def _on_lock(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is not None and new.state == "unlocked":
            self._start_timer("auto_lock", self._auto_lock_delay, self._check_auto_lock)
        elif new is not None and new.state == "locked":
            self._cancel_timer("auto_lock")

    @callback
    def _on_ignition(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        old = event.data["old_state"]
        if new is None or new.state in BAD_STATES:
            return
        off = new.state.upper() == "OFF"
        was_off = old is not None and str(old.state).upper() == "OFF"
        if off and not was_off:
            self._start_timer("auto_lock", self._auto_lock_delay, self._check_auto_lock)
            self._start_timer(
                "garage_close",
                self.numbers["garage_close_delay"] * 60,
                self._check_garage_close,
            )
            if self._doors_open():
                self._start_timer("door_open", self._door_open_delay, self._check_door_open)
                self._schedule_door_recheck()
        elif not off:
            self._cancel_timer("garage_close")
            self._cancel_timer("door_open")
            # Back in the vehicle: earlier notifications are no longer news.
            self._clear("start", "autolock", "nightlock", "garage", "plugin", "charge")
            if self._activity_active:
                self.hass.async_create_task(self._activity_end())

    @callback
    def _on_doors(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is None or new.state in BAD_STATES:
            return
        if new.state == "Closed":
            self._cancel_timer("door_open")
            self._cancel_timer("door_recheck")
            self._door_rechecked = False
            self._latch("door", (False, False))
            # Doors just closed while unlocked: restart the wait.
            if self._is(self.entities.get("lock"), "unlocked"):
                self._start_timer("auto_lock", self._auto_lock_delay, self._check_auto_lock)
        elif new.state == "Open" and self._ignition_off():
            if "door_open" not in self._timers:
                self._start_timer("door_open", self._door_open_delay, self._check_door_open)
            self._schedule_door_recheck()

    @callback
    def _schedule_door_recheck(self) -> None:
        """Ask the vehicle for a fresh status once if a door still looks open.

        Ford often reports the driver's door ajar in the update sent as the
        ignition turns off, and the vehicle may not report again when it closes.
        """
        if self._door_rechecked or "refresh" not in self.entities or "door_recheck" in self._timers:
            return
        self._start_timer("door_recheck", DOOR_RECHECK_DELAY, self._door_recheck)

    async def _door_recheck(self) -> None:
        if not (self._doors_open() and self._ignition_off()) or self._door_rechecked:
            return
        self._door_rechecked = True
        _LOGGER.debug("%s: door still reported open, requesting a vehicle status refresh", self.name)
        await self._call("button", "press", "refresh")

    def _open_door_text(self) -> tuple[str, bool]:
        """Which doors are open, and whether that's more than one."""
        state = self._state("doors")
        doors = open_doors(state.attributes) if state else []
        if not doors:
            return "A door", False
        if len(doors) == 1:
            return doors[0], False
        return ", ".join(doors[:-1]) + " and " + doors[-1].lower(), True

    async def _check_door_open(self) -> None:
        if not (self.features["door_open_alert"] and self._doors_open() and self._ignition_off()):
            return
        if not self._latch("door", (True, True)):
            return
        minutes = round(self.numbers["door_open_delay"])
        doors, plural = self._open_door_text()
        await self._notify(
            "door",
            f"🚪 {self.name} door open",
            f"{doors} {'have' if plural else 'has'} been open for {minutes} minutes.",
            time_sensitive=True,
        )

    def _walked_away(self) -> bool:
        limit = self.numbers["walk_away_distance"]
        phone_id = self.options.get(CONF_PHONE_TRACKER)
        if not phone_id or limit <= 0:
            return True
        phone = self.hass.states.get(phone_id)
        car = self._state("tracker")
        if phone is None or car is None:
            return True
        try:
            meters = gps_distance(
                phone.attributes[ATTR_LATITUDE],
                phone.attributes[ATTR_LONGITUDE],
                car.attributes[ATTR_LATITUDE],
                car.attributes[ATTR_LONGITUDE],
            )
        except (KeyError, TypeError):
            return True
        if meters is None:
            return True
        return self.hass.config.units.length(meters, UnitOfLength.METERS) > limit

    async def _check_auto_lock(self) -> None:
        if not self.features["auto_lock"]:
            return
        if self._in_zone(self._home()):
            return
        if not self._is(self.entities.get("lock"), "unlocked"):
            return
        if not self._ignition_off():
            return
        if "doors" in self.entities and self._value("doors") != "Closed":
            return
        if not self._walked_away():
            # Still near the vehicle; check again after another wait.
            self._start_timer("auto_lock", self._auto_lock_delay, self._check_auto_lock)
            return
        if await self._call("lock", "lock", "lock"):
            await self._notify(
                "autolock",
                f"{self.name} locked",
                "Doors were left unlocked away from home, so Home Assistant locked them.",
                actions=["HONK"] if "honk" in self.entities else None,
            )

    async def _night_lock(self) -> None:
        if not self.features["night_lock"]:
            return
        if not self._is(self.entities.get("lock"), "unlocked") or not self._ignition_off():
            return
        if self._doors_open():
            # Can't lock with a door open; say so (once) instead.
            if self._latch("door", (True, True)):
                doors, plural = self._open_door_text()
                await self._notify(
                    "door",
                    f"🚪 {self.name} couldn't lock for the night",
                    f"{doors} {'are' if plural else 'is'} open.",
                    time_sensitive=True,
                )
            return
        if await self._call("lock", "lock", "lock"):
            await self._notify(
                "nightlock",
                f"{self.name} locked for the night",
                "It was still unlocked, so Home Assistant locked it.",
                actions=["HONK"] if "honk" in self.entities else None,
            )

    # ------------------------------------------------- remote start features

    async def _precondition(self) -> None:
        if not (
            self.features["precondition"]
            and self._today_in(CONF_PRECONDITION_DAYS)
            and self._in_zone(self._home())
            and self._ignition_off()
            and self._is(self.entities.get("remote_start"), "off")
            and self._fuel_ok_to_start()
            and self._temp_wants_start()
        ):
            return
        if await self._call("switch", "turn_on", "remote_start"):
            title = f"{self.name} is warming up"
            message = f"{self._temp_text()}Remote started."
            if self._activity_enabled() or self.features["status_activity"]:
                # A Live Activity shows it instead.
                self._record("start", title, message)
            else:
                await self._notify("start", title, message, actions=["STOP"])

    async def _work_prompt(self) -> None:
        if not (
            self.features["work_prompt"]
            and self._today_in(CONF_WORK_PROMPT_DAYS)
            and self._in_zone(self.options.get(CONF_WORK_ZONE))
            and self._is(self.entities.get("remote_start"), "off")
            and self._fuel_ok_to_start()
            and self._temp_wants_start()
        ):
            return
        await self._notify(
            "start",
            f"Start the {self.name}?",
            f"{self._temp_text()}Tap Start to remote start before you head out.",
            actions=["START"],
        )

    @callback
    def _on_remote_start(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None:
            return
        if new.state == "off" and old is not None and old.state == "on":
            self._clear("start")
            if self._activity_active:
                self.hass.async_create_task(self._activity_end())
        elif new.state == "on" and (old is None or old.state != "on") and not self._activity_active:
            self._schedule_activity_update()

    # ----------------------------------------------- remote start Live Activity

    @property
    def _activity_tag(self) -> str:
        return f"ford-activity-{self.vin}"

    def _activity_enabled(self) -> bool:
        # With the status activity on, remote start shows there instead.
        return (
            self.features["remote_start_activity"]
            and not self.features["status_activity"]
            and bool(self.options.get(CONF_NOTIFY_DEVICES))
        )

    def _activity_due(self, minutes: float | None) -> bool:
        """Send a new update only when the phone's own countdown would be wrong.

        The phone counts down by itself (chronometer), and iOS throttles
        frequent Live Activity updates, so only re-send when the remaining
        time jumps (an extend, or the first real reading).
        """
        if not self._activity_active or self._activity_sent_minutes is None:
            return True
        if minutes is None or self._activity_sent_at is None:
            return False
        elapsed = (dt_util.utcnow() - self._activity_sent_at).total_seconds() / 60
        expected = self._activity_sent_minutes - elapsed
        return abs(minutes - expected) >= 1.5

    @callback
    def _schedule_activity_update(self) -> None:
        """Queue one Live Activity push; extra requests before it runs are merged."""
        if self._activity_pending:
            return
        self._activity_pending = True

        async def _run() -> None:
            try:
                await self._activity_update()
            finally:
                self._activity_pending = False

        self.hass.async_create_task(_run())

    async def _activity_update(self) -> None:
        if not self._activity_enabled() or not self._is(self.entities.get("remote_start"), "on"):
            return
        state = self._state("countdown")
        minutes = (
            countdown_minutes(state.state, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))
            if state
            else None
        )
        temp = self._number("temperature")
        parts = ["Remote start running"]
        if temp is not None:
            parts.append(f"{round(temp)}° outside")
        if minutes:
            parts.append(f"{round(minutes)} min left")
        data: dict[str, Any] = {
            "tag": self._activity_tag,
            "live_update": True,
            "critical_text": "Running",
            "notification_icon": "mdi:car-key",
            "notification_icon_color": ACTIVITY_COLOR,
            "color": ACTIVITY_COLOR,
        }
        if minutes and minutes > 0:
            data["chronometer"] = True
            data["when"] = int(minutes * 60)
            data["when_relative"] = True
        commands = ["STOP"]
        if "extend" in self.entities:
            commands.append("EXTEND")
        data["actions"] = self._actions(commands)
        if url := self._tap_url():
            data["url"] = url
            data["clickAction"] = url
        self._activity_active = True
        self._activity_sent_minutes = minutes
        self._activity_sent_at = dt_util.utcnow()
        await self._deliver(
            {"title": f"{self.name}", "message": " · ".join(parts), "data": data}
        )

    async def _activity_end(self) -> None:
        if not self._activity_active:
            return
        self._activity_active = False
        self._activity_sent_minutes = None
        self._activity_sent_at = None
        await self._deliver(
            {"message": "clear_notification", "data": {"tag": self._activity_tag}}
        )

    @callback
    def _on_countdown(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is None:
            return
        minutes = countdown_minutes(new.state, new.attributes.get(ATTR_UNIT_OF_MEASUREMENT))
        previous, self._last_countdown = self._last_countdown, minutes
        if (
            minutes
            and self._activity_enabled()
            and self._is(self.entities.get("remote_start"), "on")
            and self._activity_due(minutes)
        ):
            self._schedule_activity_update()
        if minutes is None or not self.features["auto_extend"]:
            return
        limit = self.numbers["extend_below"]
        crossed = 0 < minutes < limit and (previous is None or previous >= limit)
        if not crossed or "extend" not in self.entities:
            return
        if not self._is(self.entities.get("remote_start"), "on") or not self._ignition_off():
            return
        now = dt_util.utcnow()
        if self._last_extend and (now - self._last_extend).total_seconds() < EXTEND_COOLDOWN:
            return
        self._last_extend = now
        self.hass.async_create_task(self._extend())

    async def _extend(self) -> None:
        if await self._call("button", "press", "extend"):
            self._record("extend", f"{self.name} remote start extended")

    # ---------------------------------------------------------------- alerts

    @callback
    def _on_alarm(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None or not self.features["alarm_alert"]:
            return
        normal = self.options.get(CONF_ALARM_NORMAL_STATES) or DEFAULT_ALARM_NORMAL_STATES
        if new.state in normal:
            self._clear("alarm")
            return
        if new.state in BAD_STATES:
            return
        if old is not None and old.state == new.state:
            return
        actions = [cmd for cmd, role in (("LOCK", "lock"), ("HONK", "honk")) if role in self.entities]
        self.hass.async_create_task(
            self._notify(
                "alarm",
                f"🚨 {self.name} alarm",
                f"Alarm status: {new.state}",
                actions=actions,
                critical=True,
            )
        )

    @callback
    def _on_windows(self, event: Event[EventStateChangedData]) -> None:
        if self._windows_open():
            if "windows" not in self._timers:
                self._start_timer("windows", WINDOW_OPEN_DELAY, self._check_windows)
        else:
            self._cancel_timer("windows")
            self._latch("windows", (False, False))

    @callback
    def _on_hourly(self, _now: datetime) -> None:
        if self._windows_open():
            self.hass.async_create_task(self._check_windows())

    async def _check_windows(self) -> None:
        weather = self.options.get(CONF_WEATHER)
        if not (self.features["windows_alert"] and weather and self._windows_open()):
            return
        if self.latched.get("windows"):
            return
        forecast: list[dict[str, Any]] = []
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly"},
                target={ATTR_ENTITY_ID: weather},
                blocking=True,
                return_response=True,
            )
            forecast = (response or {}).get(weather, {}).get("forecast", [])
        except HomeAssistantError as err:
            _LOGGER.debug("Hourly forecast unavailable for %s: %s", weather, err)
        current = self.hass.states.get(weather)
        if not rain_expected(current.state if current else None, forecast):
            return
        self._latch("windows", (True, True))
        await self._notify(
            "windows",
            f"{self.name} windows are open",
            "Rain is expected in the next few hours.",
        )

    @callback
    def _on_fuel(self, event: Event[EventStateChangedData]) -> None:
        if not self.features["fuel_alert"]:
            return
        level, _source, _range = self._energy()
        if self._latch("fuel", percent_alert(level, self.numbers["fuel_threshold"], self.latched.get("fuel", False))):
            self.hass.async_create_task(self._fuel_notification())

    async def _fuel_notification(self) -> None:
        level, source, energy_range = self._energy()
        if level is None:
            return
        extra = f" (about {round(energy_range)} range)" if energy_range is not None else ""
        title = (
            f"⛽ {self.name} fuel is low"
            if source == "fuel"
            else f"🔋 {self.name} battery is low"
        )
        await self._notify("fuel", title, f"{round(level)}% left{extra}.")

    @callback
    def _on_oil(self, event: Event[EventStateChangedData]) -> None:
        if not self.features["oil_alert"]:
            return
        oil = self._number("oil")
        if self._latch("oil", percent_alert(oil, self.numbers["oil_threshold"], self.latched.get("oil", False))):
            self.hass.async_create_task(self._oil_notification(oil))

    async def _oil_notification(self, oil: float | None) -> None:
        await self._notify(
            "oil", f"🛢️ {self.name} oil change due", f"Oil life is at {round(oil or 0)}%."
        )
        if todo := self.options.get(CONF_TODO):
            try:
                await self.hass.services.async_call(
                    "todo",
                    "add_item",
                    {"item": f"Oil change – {self.name}"},
                    target={ATTR_ENTITY_ID: todo},
                    blocking=True,
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Could not add oil change to %s: %s", todo, err)

    @callback
    def _on_battery(self, event: Event[EventStateChangedData]) -> None:
        if not self.features["battery_alert"]:
            return
        battery = self._number("battery")
        if self._latch("battery", percent_alert(battery, self.numbers["battery_threshold"], self.latched.get("battery", False))):
            state = self._state("battery")
            volts = state.attributes.get("batteryVoltage") if state else None
            extra = f" ({volts} V)" if volts is not None else ""
            self.hass.async_create_task(
                self._notify("battery", f"🔋 {self.name} 12V battery low", f"{round(battery or 0)}%{extra}.")
            )

    @callback
    def _on_tires(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is None or new.state in BAD_STATES or not self.features["tire_alert"]:
            return
        if self._latch("tires", state_alert(new.state != "NORMAL_OPERATION", self.latched.get("tires", False))):
            self.hass.async_create_task(
                self._notify("tires", f"🛞 {self.name} tire pressure", tire_summary(new.state, new.attributes))
            )

    @callback
    def _on_indicators(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is None or new.state in BAD_STATES or not self.features["indicator_alert"]:
            return
        lights = active_indicators(new.attributes)
        active = (to_float(new.state) or 0) > 0
        if self._latch("indicators", state_alert(active, self.latched.get("indicators", False))):
            self.hass.async_create_task(
                self._notify(
                    "indicators",
                    f"⚠️ {self.name} warning light",
                    ", ".join(lights) or "A dashboard warning light is on.",
                )
            )

    # ---------------------------------------------------------- zones/garage

    @callback
    def _on_tracker(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None or old is None:
            return
        home = self._home()
        if self._in_zone(home, new) and not self._in_zone(home, old):
            self.hass.async_create_task(self._garage_open())
        work = self.options.get(CONF_WORK_ZONE)
        if work and self._in_zone(work, old) and not self._in_zone(work, new):
            self.hass.async_create_task(self._leaving_work_fuel())

    async def _leaving_work_fuel(self) -> None:
        # A reminder on the way home, even if the low-fuel alert already fired.
        level, _source, _range = self._energy()
        if self.features["fuel_alert"] and level is not None and level < self.numbers["fuel_threshold"]:
            await self._fuel_notification()

    async def _garage_open(self) -> None:
        garage = self.options.get(CONF_GARAGE)
        if not (self.features["garage_open"] and garage and self._is(garage, "closed")):
            return
        if await self._call("cover", "open_cover", garage):
            self._record("garage_open", f"Garage opened for the {self.name}")

    async def _check_garage_close(self) -> None:
        garage = self.options.get(CONF_GARAGE)
        if not (
            self.features["garage_close"]
            and garage
            and self._is(garage, "open")
            and self._ignition_off()
            and self._in_zone(self._home())
        ):
            return
        if await self._call("cover", "close_cover", garage):
            await self._notify(
                "garage",
                "Garage closed",
                f"The {self.name} is parked, so the garage door was closed.",
            )

    # ------------------------------------------------------------ EV / PHEV

    def _battery_text(self) -> str:
        soc = self._number("soc")
        if soc is None:
            return ""
        state = self._state("soc")
        battery_range = to_float(state.attributes.get("batteryRange")) if state else None
        extra = f" (about {round(battery_range)} range)" if battery_range is not None else ""
        return f"Battery is at {round(soc)}%{extra}."

    async def _plug_in_reminder(self) -> None:
        if not (self.features["plug_in_reminder"] and self.is_electric):
            return
        soc = self._number("soc")
        if (
            soc is None
            or soc >= self.numbers["plug_in_below"]
            or self._value("ev_plug") != PLUG_DISCONNECTED
            or not self._in_zone(self._home())
        ):
            return
        await self._notify(
            "plugin", f"🔌 Plug in the {self.name}?", self._battery_text()
        )

    @callback
    def _on_plug(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is None or new.state in BAD_STATES:
            return
        if new.state == PLUG_DISCONNECTED:
            self._clear("charge")
        else:
            self._clear("plugin")

    @callback
    def _on_charging(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None or old is None or old.state != CHARGE_IN_PROGRESS:
            return
        if new.state in BAD_STATES or new.state == CHARGE_IN_PROGRESS:
            return
        if not self.features["charge_alert"]:
            return
        if new.state in CHARGE_FAULTS:
            self.hass.async_create_task(
                self._notify(
                    "charge",
                    f"⚠️ {self.name} charging stopped",
                    (
                        "The charger wasn't detected."
                        if new.state == "STATION_NOT_DETECTED"
                        else "The charger reported a fault."
                    )
                    + (f" {self._battery_text()}" if self._battery_text() else ""),
                    time_sensitive=True,
                )
            )
        elif new.state == CHARGE_DONE:
            self.hass.async_create_task(
                self._notify(
                    "charge",
                    f"🔋 {self.name} finished charging",
                    self._battery_text() or "Charging is complete.",
                )
            )

    # ------------------------------------------------------ action buttons

    @callback
    def _on_action(self, event: Event) -> None:
        command = parse_action(event.data.get("action"), self.vin)
        if command is None:
            return
        target = {
            "LOCK": ("lock", "lock", "lock"),
            "HONK": ("button", "press", "honk"),
            "START": ("switch", "turn_on", "remote_start"),
            "STOP": ("switch", "turn_off", "remote_start"),
            "EXTEND": ("button", "press", "extend"),
        }[command]
        if target[2] not in self.entities:
            _LOGGER.warning("%s isn't available for %s", command.lower(), self.name)
            return
        self.hass.async_create_task(self._run_command(command, *target))

    async def _run_command(self, command: str, domain: str, service: str, role: str) -> None:
        if await self._call(domain, service, role):
            self._record(f"command_{command.lower()}", f"{command.title()} sent to {self.name}")

    # ------------------------------------------------------------- reload

    @callback
    def _on_registry_update(self, event: Event) -> None:
        if event.data.get("action") in ("update", "remove"):
            self.hass.config_entries.async_schedule_reload(self.entry.entry_id)
