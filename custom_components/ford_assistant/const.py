"""Constants for Ford Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DOMAIN: Final = "ford_assistant"
FORD_DOMAIN: Final = "fordpass"

EVENT_ALERT: Final = "ford_assistant_alert"
NOTIFICATION_ACTION_EVENT: Final = "mobile_app_notification_action"
ACTION_PREFIX: Final = "FORD_ASSISTANT"

# Config entry data / options
CONF_VIN: Final = "vin"
CONF_NOTIFY_DEVICES: Final = "notify_devices"
CONF_PHONE_TRACKER: Final = "phone_tracker"
CONF_HOME_ZONE: Final = "home_zone"
CONF_WORK_ZONE: Final = "work_zone"
CONF_WEATHER: Final = "weather_entity"
CONF_TODO: Final = "todo_entity"
CONF_GARAGE: Final = "garage_cover"
CONF_PRECONDITION_DAYS: Final = "precondition_days"
CONF_WORK_PROMPT_DAYS: Final = "work_prompt_days"
CONF_ALARM_NORMAL_STATES: Final = "alarm_normal_states"

WEEKDAYS: Final = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_DAYS: Final = ["mon", "tue", "wed", "thu", "fri"]
DEFAULT_ALARM_NORMAL_STATES: Final = ["ARMED", "PREARMED", "DISARMED"]

# Ford integration entity keys -> our role names.
# The Ford integration builds unique_ids as f"fordpass_uid_{vin}_{key}".lower().
FORD_ENTITY_KEYS: Final[dict[str, tuple[str, str]]] = {
    # role: (platform, key)
    "lock": ("lock", "doorlock"),
    "tracker": ("device_tracker", "tracker"),
    "ignition": ("sensor", "ignitionstatus"),
    "doors": ("sensor", "doorstatus"),
    "windows": ("sensor", "windowposition"),
    "remote_start": ("switch", "ignition"),
    "countdown": ("sensor", "remotestartcountdown"),
    "extend": ("button", "extendremotestart"),
    "honk": ("button", "hafdefault"),
    "alarm": ("sensor", "alarm"),
    "fuel": ("sensor", "fuel"),
    "oil": ("sensor", "oil"),
    "battery": ("sensor", "battery"),
    "tires": ("sensor", "tirepressure"),
    "indicators": ("sensor", "indicators"),
    "temperature": ("sensor", "outsidetemp"),
    "refresh": ("button", "request_refresh"),
    # Electric and plug-in hybrid vehicles
    "soc": ("sensor", "soc"),
    "ev_plug": ("sensor", "elvehplug"),
    "ev_charging": ("sensor", "elvehcharging"),
}
EV_ROLES: Final = ("soc", "ev_plug", "ev_charging")
REQUIRED_ROLES: Final = ("lock", "tracker")

# Feature switches: key -> default
FEATURES: Final[dict[str, bool]] = {
    "auto_lock": True,
    "precondition": False,
    "work_prompt": False,
    "auto_extend": False,
    "alarm_alert": True,
    "windows_alert": True,
    "fuel_alert": True,
    "oil_alert": True,
    "battery_alert": True,
    "tire_alert": True,
    "indicator_alert": True,
    "garage_open": True,
    "garage_close": True,
    "night_lock": True,
    "door_open_alert": True,
    "clear_resolved": True,
    "quiet_hours": False,
    "remote_start_activity": True,
    "status_activity": False,
    "plug_in_reminder": True,
    "charge_alert": True,
}

# Only created for electric and plug-in hybrid vehicles.
EV_FEATURES: Final = frozenset({"plug_in_reminder", "charge_alert"})
EV_NUMBERS: Final = frozenset({"plug_in_below"})
EV_TIMES: Final = frozenset({"plug_in_time"})


@dataclass(frozen=True, slots=True)
class NumberSpec:
    """A user-adjustable number setting."""

    default: float
    min: float
    max: float
    step: float
    unit: str | None = None


NUMBERS: Final[dict[str, NumberSpec]] = {
    "auto_lock_delay": NumberSpec(3, 1, 60, 1, "min"),
    "walk_away_distance": NumberSpec(0.05, 0, 1, 0.01),
    "cold_threshold": NumberSpec(32, -40, 120, 1),
    "hot_threshold": NumberSpec(85, -40, 120, 1),
    "min_fuel_to_start": NumberSpec(15, 0, 100, 1, "%"),
    "extend_below": NumberSpec(2, 1, 10, 1, "min"),
    "fuel_threshold": NumberSpec(15, 1, 100, 1, "%"),
    "oil_threshold": NumberSpec(10, 1, 100, 1, "%"),
    "battery_threshold": NumberSpec(60, 1, 100, 1, "%"),
    "garage_close_delay": NumberSpec(10, 1, 120, 1, "min"),
    "door_open_delay": NumberSpec(10, 1, 120, 1, "min"),
    "plug_in_below": NumberSpec(50, 5, 100, 5, "%"),
}

TIMES: Final[dict[str, str]] = {
    "precondition_time": "07:30:00",
    "work_prompt_time": "16:45:00",
    "night_lock_time": "22:00:00",
    "quiet_start": "22:00:00",
    "quiet_end": "07:00:00",
    "plug_in_time": "21:00:00",
}

# Alerts that fire once, then re-arm when the condition clears.
LATCHED_ALERTS: Final = (
    "fuel", "oil", "battery", "tires", "indicators", "windows", "door"
)

# Re-arm hysteresis for percentage alerts (points above threshold).
REARM_MARGIN: Final = 5

WINDOW_OPEN_DELAY: Final = 600  # seconds
# A door reported open as you park is often a snapshot taken while you were
# getting out; ask the vehicle for a fresh status after this long to confirm.
DOOR_RECHECK_DELAY: Final = 120  # seconds
WET_CONDITIONS: Final = frozenset(
    {"rainy", "pouring", "lightning-rainy", "snowy-rainy", "snowy", "hail"}
)

COMMANDS: Final = ("LOCK", "HONK", "START", "STOP", "EXTEND")

# Ford integration charging states
PLUG_DISCONNECTED: Final = "DISCONNECTED"
CHARGE_IN_PROGRESS: Final = "IN_PROGRESS"
CHARGE_DONE: Final = "STOPPED"
CHARGE_FAULTS: Final = frozenset({"FAULT", "STATION_NOT_DETECTED"})

ACTIVITY_COLOR: Final = "#1F6FD1"

STORAGE_VERSION: Final = 1
