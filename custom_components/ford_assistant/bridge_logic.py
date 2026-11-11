"""Normalise FordPass China readings into the values Ford Assistant expects.

The Ford integration marq24 builds exposes one aggregate entity per role (a lock
with ``locked``/``unlocked``, a doors sensor with upper-case attributes, a tire
sensor reading ``NORMAL_OPERATION``). The FordPass China integration reports the
same car as separate, localised entities. These helpers translate those values,
so the rest of Ford Assistant (alerts, dashboard, driving modes) needs no idea
which integration the vehicle came from.

Keep this module free of Home Assistant imports: the mappings are pure and are
tested on their own.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

BAD_VALUES = frozenset(
    {"", "none", "null", "unknown", "unavailable", "未知", "不可用", "无"}
)

# Attribute names the rest of Ford Assistant already knows: messages.door_name
# and the dashboard read these keys, and upper-case values mark an open door.
DOORS: tuple[tuple[str, str], ...] = (
    ("driverFront", "driver_door"),
    ("passengerFront", "passenger_door"),
    ("driverRear", "left_rear_door"),
    ("passengerRear", "right_rear_door"),
    ("tailgate", "tailgate"),
    ("hood", "hood"),
    ("innerTailgate", "inner_tailgate"),
)

WINDOWS: tuple[tuple[str, str], ...] = (
    ("driver", "driver_window"),
    ("passenger", "passenger_window"),
    ("driverRear", "left_rear_window"),
    ("passengerRear", "right_rear_window"),
    ("sunroof", "sunroof"),
)

TIRES: tuple[tuple[str, str, str], ...] = (
    ("frontLeft", "lf_tire", "lf_tire_status"),
    ("frontRight", "rf_tire", "rf_tire_status"),
    ("rearLeft", "lr_tire", "lr_tire_status"),
    ("rearRight", "rr_tire", "rr_tire_status"),
)

_CLOSED = frozenset({"closed", "close", "已关闭", "关闭"})
_OPEN = frozenset({"open", "opened", "ajar", "已打开", "未关紧"})
_LOCKED = frozenset({"locked", "已锁定"})
_UNLOCKED = frozenset({"unlocked", "已解锁"})
_IGNITION_OFF = frozenset({"off", "已熄火"})
_IGNITION_ON = frozenset({"on", "run", "已启动", "运行中"})
_REMOTE_ON = frozenset({"on", "true", "1", "已远程启动"})
_REMOTE_OFF = frozenset({"off", "false", "0", "未远程启动"})
_PLUGGED = frozenset({"connected", "已连接"})
_UNPLUGGED = frozenset({"disconnected", "unplugged", "未连接", "未插枪"})
_CHARGING = frozenset({"charging", "in_progress", "充电中"})
_CHARGED = frozenset(
    {"stopped", "complete", "completed", "charged", "已充满", "已完成", "未充电"}
)
_CHARGE_FAULT = frozenset({"fault", "故障", "充电故障"})
_TIRE_OK = frozenset({"normal", "ok", "正常"})
_TIRE_FAULT = frozenset({"fault", "故障"})

_ALARM_ARMED = frozenset({"armed", "set", "车辆已设防", "已设防"})
_ALARM_DISARMED = frozenset(
    {
        "disarmed",
        "notset",
        "not_in_alarm",
        "not_in_alarms",
        "解除报警",
        "车辆未设防",
        "未设防",
    }
)
_ALARM_TRIGGERED = frozenset({"alarm", "被盗声光报警中", "报警中"})


def text(value: Any) -> str:
    """A stripped string, or ``""`` for nothing usable."""
    if value is None:
        return ""
    return str(value).strip()


def is_bad(value: Any) -> bool:
    """Whether a state carries no information."""
    return text(value).lower() in BAD_VALUES


def number(value: Any) -> float | None:
    """A float from a state, or None."""
    if isinstance(value, bool) or is_bad(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(text(value).replace(",", "."))
    except ValueError:
        return None


def door_state(value: Any) -> str | None:
    """``Closed``, ``Open`` or None for a door reading."""
    raw = text(value).lower()
    if raw in _CLOSED:
        return "Closed"
    if raw in _OPEN:
        return "Open"
    return None


def window_state(value: Any) -> str | None:
    """``Closed``/``Open``; the China integration also reports percentages."""
    raw = text(value)
    if not raw:
        return None
    low = raw.lower()
    if low in {"closed", "close"} or raw in {"已关闭", "关闭"}:
        return "Closed"
    if low in {"unknown", "not supported", "not_supported", "null", "未知"}:
        return None
    # "未关闭（全开）", "未关闭 10%", "fully open", ...
    return "Open"


def lock_state(value: Any) -> str | None:
    """``locked``, ``unlocked`` or None."""
    raw = text(value).lower()
    if raw in _LOCKED:
        return "locked"
    if raw in _UNLOCKED:
        return "unlocked"
    return None


def ignition_state(value: Any) -> str | None:
    """``ON``, ``OFF`` or None."""
    raw = text(value).lower()
    if raw in _IGNITION_OFF:
        return "OFF"
    if raw in _IGNITION_ON:
        return "ON"
    return None


def remote_start_state(value: Any) -> str | None:
    """``on``, ``off`` or None."""
    raw = text(value).lower()
    if raw in _REMOTE_ON:
        return "on"
    if raw in _REMOTE_OFF:
        return "off"
    return None


def alarm_state(value: Any) -> str | None:
    """``ARMED``, ``DISARMED``, ``ALARM`` or None."""
    raw = text(value)
    low = raw.lower()
    if low in _ALARM_TRIGGERED:
        return "ALARM"
    if low in _ALARM_ARMED:
        return "ARMED"
    if low in _ALARM_DISARMED:
        return "DISARMED"
    return None


def plug_state(value: Any) -> str | None:
    """``CONNECTED``, ``DISCONNECTED`` or None."""
    raw = text(value).lower()
    if raw in _PLUGGED:
        return "CONNECTED"
    if raw in _UNPLUGGED:
        return "DISCONNECTED"
    return None


def charging_state(value: Any) -> str | None:
    """``IN_PROGRESS``, ``STOPPED``, ``FAULT`` or None."""
    raw = text(value).lower()
    if raw in _CHARGING:
        return "IN_PROGRESS"
    if raw in _CHARGE_FAULT:
        return "FAULT"
    if raw in _CHARGED:
        return "STOPPED"
    return None


def tire_state(value: Any) -> str | None:
    """``NORMAL``, ``WARNING``, ``FAULT`` or None for one wheel."""
    raw = text(value).lower()
    if raw in _TIRE_OK:
        return "NORMAL"
    if raw in _TIRE_FAULT:
        return "FAULT"
    if raw in {"not_supported", "not supported", "不支持", "unknown", "未知"}:
        return None
    return "WARNING" if raw else None


def doors(states: Mapping[str, Any]) -> tuple[str | None, dict[str, str]]:
    """The aggregate doors state and its upper-case attributes."""
    attributes: dict[str, str] = {}
    for attribute, key in DOORS:
        if (state := door_state(states.get(key))) is not None:
            attributes[attribute] = "OPEN" if state == "Open" else "CLOSED"
    if not attributes:
        return None, {}
    open_door = any(value == "OPEN" for value in attributes.values())
    return ("Open" if open_door else "Closed"), attributes


def windows(states: Mapping[str, Any]) -> str | None:
    """Whether any window is open."""
    seen = False
    for _attribute, key in WINDOWS:
        state = window_state(states.get(key))
        if state is None:
            continue
        seen = True
        if state == "Open":
            return "Open"
    return "Closed" if seen else None


def tires(
    pressures: Mapping[str, Any], statuses: Mapping[str, Any]
) -> tuple[str | None, dict[str, Any]]:
    """The aggregate tire state and its per-wheel attributes."""
    attributes: dict[str, Any] = {}
    for attribute, pressure_key, status_key in TIRES:
        if (pressure := number(pressures.get(pressure_key))) is not None:
            attributes[attribute] = int(pressure)
        if (state := tire_state(statuses.get(status_key))) is not None:
            attributes[f"{attribute}_state"] = state
    if not attributes:
        return None, {}
    bad = any(
        attributes.get(f"{attribute}_state") not in (None, "NORMAL")
        for attribute, _pressure, _status in TIRES
    )
    return ("WARNING" if bad else "NORMAL_OPERATION"), attributes
