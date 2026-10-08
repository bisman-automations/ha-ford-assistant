"""Tests for the pure helpers."""

from custom_components.ford_assistant.logic import (
    action_id,
    active_indicators,
    countdown_minutes,
    parse_action,
    percent_alert,
    rain_expected,
    state_alert,
    temp_wants_start,
    tire_summary,
)

VIN = "1FMSK8DH8NGC00000"


def test_action_round_trip() -> None:
    assert action_id("START", VIN.lower()) == f"FORD_ASSISTANT_START_{VIN}"
    assert parse_action(action_id("STOP", VIN), VIN) == "STOP"
    assert parse_action(action_id("STOP", VIN), "OTHERVIN") is None
    assert parse_action(f"FORD_ASSISTANT_NUKE_{VIN}", VIN) is None
    assert parse_action(None, VIN) is None


def test_countdown_units() -> None:
    assert countdown_minutes("2", "min") == 2
    assert countdown_minutes("90", "s") == 1.5
    assert countdown_minutes("unavailable", "min") is None


def test_temp_wants_start() -> None:
    assert temp_wants_start(20, 32, 85)
    assert temp_wants_start(90, 32, 85)
    assert not temp_wants_start(60, 32, 85)
    assert not temp_wants_start(None, 32, 85)


def test_percent_alert_fires_once_and_rearms() -> None:
    fire, latched = percent_alert(10, 15, False)
    assert fire and latched
    fire, latched = percent_alert(9, 15, latched)
    assert not fire and latched
    # Hovering just above the threshold stays latched.
    fire, latched = percent_alert(17, 15, latched)
    assert not fire and latched
    fire, latched = percent_alert(25, 15, latched)
    assert not fire and not latched
    fire, _ = percent_alert(12, 15, latched)
    assert fire


def test_state_alert() -> None:
    assert state_alert(True, False) == (True, True)
    assert state_alert(True, True) == (False, True)
    assert state_alert(False, True) == (False, False)


def test_rain_expected() -> None:
    assert rain_expected("rainy", [])
    assert rain_expected("sunny", [{"condition": "cloudy"}, {"condition": "pouring"}])
    assert rain_expected("sunny", [{"condition": "cloudy", "precipitation_probability": 60}])
    assert not rain_expected("sunny", [{"condition": "cloudy", "precipitation_probability": 20}])
    # Only the next three hours count.
    assert not rain_expected("sunny", [{"condition": "sunny"}] * 3 + [{"condition": "rainy"}])


def test_active_indicators() -> None:
    attrs = {"checkEngineLight": True, "lowTirePressure_frontLeft": True, "absWarning": False}
    assert active_indicators(attrs) == ["Check engine light", "Low tire pressure"]


def test_tire_summary() -> None:
    attrs = {
        "frontLeft": "32.0 psi",
        "frontLeft_state": "LOW_PRESSURE",
        "frontRight": "35.0 psi",
        "rearLeft": "35.0 psi",
        "rearRight": "35.0 psi",
    }
    text = tire_summary("SYSTEM_WARNING", attrs)
    assert text.startswith("System warning. Front left: 32.0 psi ⚠️ Low pressure")
    assert "Rear right: 35.0 psi" in text


def test_open_doors() -> None:
    from custom_components.ford_assistant.logic import open_doors

    attrs = {"driverFront": "OPEN", "passengerFront": "CLOSED", "hood": "AJAR", "tailgate": "INVALID"}
    assert open_doors(attrs) == ["Driver front", "Hood"]


def test_open_doors_ignores_ha_attributes() -> None:
    from custom_components.ford_assistant.logic import open_doors

    attrs = {
        "driverFront": "AJAR",
        "rearLeft": "CLOSED",
        "icon": "mdi:car-door",
        "friendly_name": "Doors",
    }
    assert open_doors(attrs) == ["Driver front"]
