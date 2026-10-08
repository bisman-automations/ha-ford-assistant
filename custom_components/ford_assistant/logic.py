"""Pure helpers: no Home Assistant state access, easy to unit test."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import time
import re
from typing import Any

from .const import ACTION_PREFIX, COMMANDS, REARM_MARGIN, WET_CONDITIONS

TIRE_POSITIONS = ("frontLeft", "frontRight", "rearLeft", "rearRight")
TIRE_LABELS = {
    "frontLeft": "Front left",
    "frontRight": "Front right",
    "rearLeft": "Rear left",
    "rearRight": "Rear right",
}


def in_quiet_hours(now: time, start: time, end: time) -> bool:
    """Whether a time falls inside quiet hours (which may span midnight)."""
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def to_float(value: Any) -> float | None:
    """Parse a state value, returning None for unknown/unavailable."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def countdown_minutes(value: Any, unit: str | None) -> float | None:
    """Convert the Ford remote-start countdown state to minutes."""
    number = to_float(value)
    if number is None:
        return None
    match (unit or "").lower():
        case "s" | "sec" | "seconds":
            return number / 60
        case "h" | "hours":
            return number * 60
        case _:
            # The Ford integration suggests minutes as the display unit.
            return number


def temp_wants_start(temp: float | None, cold: float, hot: float) -> bool:
    """Whether the outside temperature justifies a remote start."""
    return temp is not None and (temp < cold or temp > hot)


def action_id(command: str, vin: str) -> str:
    """Build a notification action id for a command and vehicle."""
    return f"{ACTION_PREFIX}_{command}_{vin.upper()}"


def parse_action(action: str | None, vin: str) -> str | None:
    """Return the command if the action belongs to this vehicle."""
    if not action:
        return None
    match = re.fullmatch(rf"{ACTION_PREFIX}_([A-Z]+)_{re.escape(vin.upper())}", action)
    if match and match.group(1) in COMMANDS:
        return match.group(1)
    return None


def percent_alert(
    value: float | None, threshold: float, latched: bool
) -> tuple[bool, bool]:
    """Evaluate a low-percentage alert.

    Returns (fire, latched_after). Fires once when the value drops below the
    threshold and re-arms only after it recovers REARM_MARGIN points above it,
    so a value hovering around the threshold doesn't spam notifications.
    """
    if value is None:
        return False, latched
    if value < threshold:
        return (not latched), True
    if value >= threshold + REARM_MARGIN:
        return False, False
    return False, latched


def state_alert(active: bool, latched: bool) -> tuple[bool, bool]:
    """Evaluate an on/off alert. Returns (fire, latched_after)."""
    if active:
        return (not latched), True
    return False, False


def rain_expected(
    current: str | None, forecast: Iterable[Mapping[str, Any]], hours: int = 3
) -> bool:
    """Whether rain (or similar) is happening now or expected soon."""
    if current in WET_CONDITIONS:
        return True
    for item in list(forecast)[:hours]:
        if item.get("condition") in WET_CONDITIONS:
            return True
        probability = to_float(item.get("precipitation_probability"))
        if probability is not None and probability >= 50:
            return True
    return False


def active_indicators(attributes: Mapping[str, Any]) -> list[str]:
    """Readable names of the warning lights that are on."""
    names: list[str] = []
    for key, value in attributes.items():
        if value is not True:
            continue
        base = re.sub(r"_[0-9A-Za-z]+$", "", key) if "_" in key else key
        names.append(humanize(base))
    return names


def open_doors(attributes: Mapping[str, Any]) -> list[str]:
    """Readable names of the doors (and hood) that are open.

    Only door values count (upper-case states like OPEN or AJAR); Home
    Assistant's own attributes on the sensor (icon, friendly_name) are skipped.
    """
    closed = {"CLOSED", "INVALID", "UNKNOWN", "UNSUPPORTED"}
    return [
        humanize(key)
        for key, value in attributes.items()
        if isinstance(value, str)
        and re.fullmatch(r"[A-Z_]+", value)
        and value not in closed
    ]


def humanize(key: str) -> str:
    """camelCase -> 'Camel case'."""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", key).lower()
    return words[:1].upper() + words[1:]


def tire_summary(state: str, attributes: Mapping[str, Any]) -> str:
    """Describe tire pressures, flagging any wheel that isn't normal."""
    parts: list[str] = []
    for pos in TIRE_POSITIONS:
        pressure = attributes.get(pos)
        wheel_state = attributes.get(f"{pos}_state")
        if pressure is None and wheel_state is None:
            continue
        text = f"{TIRE_LABELS[pos]}: {pressure if pressure is not None else '?'}"
        if wheel_state not in (None, "NORMAL"):
            text += f" ⚠️ {humanize_enum(wheel_state)}"
        parts.append(text)
    status = humanize_enum(state)
    return f"{status}. " + ", ".join(parts) if parts else f"{status}."


def humanize_enum(value: str) -> str:
    """LOW_PRESSURE -> 'Low pressure'."""
    text = str(value).replace("_", " ").lower()
    return text[:1].upper() + text[1:]


def notify_service_name(device_name: str) -> str:
    """mobile_app notify service name for a registered device name."""
    from homeassistant.util import slugify  # local import keeps this module light

    return f"mobile_app_{slugify(device_name)}"
