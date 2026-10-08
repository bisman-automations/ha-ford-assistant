"""Always-on vehicle status Live Activity.

Keeps one Live Activity (Live Update on Android) on the phone showing the
vehicle's lock state, doors and windows, fuel or battery, where it is, and
whether it's running. It only pushes when something visible changes, merges
bursts of sensor updates, and restarts itself before iOS's 8-hour limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import ACTIVITY_COLOR, CHARGE_IN_PROGRESS, PLUG_DISCONNECTED
from .logic import countdown_minutes, open_doors

if TYPE_CHECKING:
    from .controller import FordAssistantController

_LOGGER = logging.getLogger(__name__)

WATCHED_ROLES = (
    "lock",
    "doors",
    "windows",
    "ignition",
    "remote_start",
    "countdown",
    "alarm",
    "fuel",
    "soc",
    "tracker",
    "temperature",
    "ev_plug",
    "ev_charging",
)
ATTENTION_COLOR = "#E5484D"
DEBOUNCE = 5  # seconds: the Ford integration updates many sensors at once
MINOR_INTERVAL = timedelta(minutes=5)  # at most one quiet update per 5 minutes
RESTART_AFTER = timedelta(hours=7, minutes=45)  # iOS ends activities at 8 hours
BAD = (STATE_UNKNOWN, STATE_UNAVAILABLE, None)


@dataclass(frozen=True)
class StatusView:
    """What the activity shows; compared to decide whether to push."""

    headline: str
    message: str
    attention: bool
    level: int | None
    running_until: int | None  # epoch seconds, rounded to the minute


class StatusActivity:
    """Owns the vehicle status Live Activity for one vehicle."""

    def __init__(self, controller: FordAssistantController) -> None:
        """Initialise."""
        self.c = controller
        self.hass = controller.hass
        self._unsubs: list[CALLBACK_TYPE] = []
        self._debounce: CALLBACK_TYPE | None = None
        self._last_view: StatusView | None = None
        self._last_sent: datetime | None = None
        self.started_at: datetime | None = None

    @property
    def tag(self) -> str:
        """Notification tag for the activity."""
        return f"ford-status-{self.c.vin}"

    @property
    def enabled(self) -> bool:
        """Whether the status activity should be showing."""
        return self.c.features["status_activity"] and bool(self.c._notify_services())

    # ---------------------------------------------------------------- life

    @callback
    def async_start(self) -> None:
        """Watch the vehicle and show the activity if it's turned on."""
        entity_ids = [self.c.entities[r] for r in WATCHED_ROLES if r in self.c.entities]
        if entity_ids:
            self._unsubs.append(
                async_track_state_change_event(self.hass, entity_ids, self._on_change)
            )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._on_interval, timedelta(minutes=15))
        )
        if self.enabled:
            self.hass.async_create_task(self._resume())

    async def _resume(self) -> None:
        """After a restart: update the activity, or start fresh if it's near iOS's limit."""
        if self.started_at and dt_util.utcnow() - self.started_at >= RESTART_AFTER:
            await self._end()
        await self.async_update(force=True)

    @callback
    def async_stop(self) -> None:
        """Stop watching (the activity itself stays until turned off)."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._debounce:
            self._debounce()
            self._debounce = None

    async def async_turned_on(self) -> None:
        """The switch was turned on."""
        await self.async_update(force=True)

    async def async_turned_off(self) -> None:
        """The switch was turned off: take it off the phones."""
        await self._end()

    # ------------------------------------------------------------- updates

    @callback
    def _on_change(self, event: Event[EventStateChangedData]) -> None:
        if not self.c.features["status_activity"]:
            return
        if self._debounce:
            self._debounce()

        @callback
        def _fire(_now: datetime) -> None:
            self._debounce = None
            self.hass.async_create_task(self.async_update())

        self._debounce = async_call_later(self.hass, DEBOUNCE, _fire)

    async def _on_interval(self, now: datetime) -> None:
        if not self.enabled:
            return
        if self.started_at and dt_util.utcnow() - self.started_at >= RESTART_AFTER:
            # Restart before iOS ends it, so it really is always there.
            await self._end()
            await self.async_update(force=True)
        elif self._last_view and self._last_view.running_until is None:
            # Pick up any quiet change that was held back by the rate limit.
            await self.async_update()

    async def async_update(self, force: bool = False) -> None:
        """Push the current status if it changed."""
        if not self.enabled:
            return
        view = self.view()
        previous = self._last_view
        if not force and view == previous:
            return
        important = (
            force
            or previous is None
            or view.headline != previous.headline
            or view.attention != previous.attention
            or view.running_until != previous.running_until
        )
        now = dt_util.utcnow()
        if not important and self._last_sent and now - self._last_sent < MINOR_INTERVAL:
            return  # a fuel/temperature/location tweak; the interval check sends it later
        self._last_view = view
        self._last_sent = now
        if self.started_at is None:
            self.started_at = now
            self.c._save()
        await self.c._deliver(self.payload(view, quiet=not important))

    async def _end(self) -> None:
        self._last_view = None
        self._last_sent = None
        self.started_at = None
        self.c._save()
        await self.c._deliver({"message": "clear_notification", "data": {"tag": self.tag}})

    # ------------------------------------------------------------- content

    def view(self) -> StatusView:
        """Work out what to show right now."""
        c = self.c
        parts: list[str] = []
        attention = False

        alarm = c._value("alarm")
        normal = c.options.get("alarm_normal_states") or ["ARMED", "PREARMED", "DISARMED"]
        alarm_going = alarm not in BAD and alarm not in normal

        running = c._is(c.entities.get("remote_start"), "on")
        ignition = c._value("ignition")
        driving = not running and ignition not in BAD and str(ignition).upper() != "OFF"

        lock = c._value("lock")
        doors_open = c._value("doors") == "Open"
        windows_open = c._value("windows") not in (*BAD, "Closed")
        home = c._in_zone(c._home())

        if alarm_going:
            headline, attention = "Alarm!", True
        elif running:
            headline = "Running"
        elif driving:
            headline = "Driving"
        elif doors_open:
            headline, attention = "Door open", True
        elif lock == "unlocked":
            headline, attention = "Unlocked", not home
        elif lock == "locked":
            headline = "Locked"
        else:
            headline = "Parked"

        if alarm_going:
            parts.append(f"🚨 Alarm: {alarm}")
        if doors_open:
            state = c._state("doors")
            names = open_doors(state.attributes) if state else []
            parts.append("🚪 " + (", ".join(names) + " open" if names else "Door open"))
        if windows_open:
            parts.append("🪟 Windows open")
            attention = attention or not home
        if headline not in ("Locked", "Unlocked") and lock in ("locked", "unlocked"):
            parts.append("🔒 Locked" if lock == "locked" else "🔓 Unlocked")

        level, source, energy_range = c._energy()
        if level is not None:
            icon = "⛽" if source == "fuel" else "🔋"
            text = f"{icon} {round(level)}%"
            if energy_range is not None:
                text += f" · {round(energy_range)} {self.hass.config.units.length_unit}"
            parts.append(text)

        if c.is_electric:
            charging = c._value("ev_charging")
            plug = c._value("ev_plug")
            if charging == CHARGE_IN_PROGRESS:
                parts.append("⚡ Charging")
            elif plug not in (*BAD, PLUG_DISCONNECTED):
                parts.append("🔌 Plugged in")

        parts.append("🏠 Home" if home else f"📍 {self._place()}")

        temp = c._number("temperature")
        if temp is not None:
            parts.append(f"{round(temp)}°")

        running_until = None
        if running:
            state = c._state("countdown")
            minutes = (
                countdown_minutes(state.state, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))
                if state
                else None
            )
            if minutes and minutes > 0:
                end = dt_util.utcnow() + timedelta(minutes=minutes)
                running_until = int(end.timestamp()) // 60 * 60

        return StatusView(
            headline=headline,
            message=" · ".join(parts),
            attention=attention,
            level=round(level) if level is not None else None,
            running_until=running_until,
        )

    def _place(self) -> str:
        tracker = self.c._state("tracker")
        if tracker is None or tracker.state in (*BAD, "not_home", "home"):
            return "Away"
        return tracker.state

    def payload(self, view: StatusView, quiet: bool = False) -> dict[str, Any]:
        """The notify payload for a view."""
        c = self.c
        color = ATTENTION_COLOR if view.attention else ACTIVITY_COLOR
        data: dict[str, Any] = {
            "tag": self.tag,
            "live_update": True,
            "critical_text": view.headline,
            "notification_icon": "mdi:car-connected" if not view.attention else "mdi:car-alert",
            "notification_icon_color": color,
            "color": color,
            "sticky": True,
            "alert_once": True,
            # Let a remote start, alarm or appliance activity take the Dynamic Island.
            "relevance_score": 0.9 if view.attention or view.running_until else 0.3,
        }
        if quiet:
            data["silent"] = True
        if view.level is not None:
            data["progress"] = view.level
            data["progress_max"] = 100
            data["progress_bar_color"] = color
        if view.running_until:
            remaining = max(0, view.running_until - int(dt_util.utcnow().timestamp()))
            data["chronometer"] = True
            data["when"] = remaining
            data["when_relative"] = True
        commands: list[str] = []
        if c._value("lock") == "unlocked" and "lock" in c.entities:
            commands.append("LOCK")
        if "remote_start" in c.entities:
            commands.append("STOP" if view.headline == "Running" else "START")
        if commands:
            data["actions"] = c._actions(commands)
        if url := c._tap_url():
            data["url"] = url
            data["clickAction"] = url
        return {"title": c.name, "message": view.message, "data": data}
