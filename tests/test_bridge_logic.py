"""The FordPass China value mappings, without Home Assistant in the way."""

from __future__ import annotations

from custom_components.ford_assistant import bridge_logic as logic


def test_doors_aggregate() -> None:
    states = {
        "driver_door": "已关闭",
        "passenger_door": "未关紧",
        "left_rear_door": "已关闭",
        "right_rear_door": "已关闭",
        "tailgate": "已关闭",
    }
    state, attributes = logic.doors(states)
    assert state == "Open"
    assert attributes["passengerFront"] == "OPEN"
    assert attributes["driverFront"] == "CLOSED"
    assert "hood" not in attributes


def test_doors_unknown_yields_nothing() -> None:
    assert logic.doors({"driver_door": "未知"}) == (None, {})


def test_windows() -> None:
    assert logic.windows({"driver_window": "已关闭"}) == "Closed"
    assert logic.windows({"driver_window": "未关闭 30%"}) == "Open"
    assert logic.windows({}) is None


def test_tires() -> None:
    pressures = {
        "lf_tire": "235",
        "rf_tire": "236",
        "lr_tire": "unknown",
        "rr_tire": "235",
    }
    statuses = {
        "lf_tire_status": "正常",
        "rf_tire_status": "正常",
        "rr_tire_status": "故障",
    }
    state, attributes = logic.tires(pressures, statuses)
    assert state == "WARNING"
    assert attributes["frontLeft"] == 235
    assert "rearLeft" not in attributes
    assert attributes["frontRight"] == 236
    assert attributes["rearRight_state"] == "FAULT"


def test_alarm_and_lock() -> None:
    assert logic.alarm_state("车辆已设防") == "ARMED"
    assert logic.alarm_state("车辆未设防") == "DISARMED"
    assert logic.alarm_state("解除报警") == "DISARMED"
    assert logic.alarm_state("被盗声光报警中") == "ALARM"
    assert logic.lock_state("已锁定") == "locked"
    assert logic.lock_state("已解锁") == "unlocked"


def test_ev_readings() -> None:
    assert logic.plug_state("已连接") == "CONNECTED"
    assert logic.plug_state("未插枪") == "DISCONNECTED"
    assert logic.charging_state("充电中") == "IN_PROGRESS"
    assert logic.charging_state("已充满") == "STOPPED"
    assert logic.charging_state("未充电") == "STOPPED"


def test_numbers_and_bad_values() -> None:
    assert logic.number("55") == 55.0
    assert logic.number("12,5") == 12.5
    assert logic.number("unknown") is None
    assert logic.number(None) is None
    assert logic.number(True) is None
