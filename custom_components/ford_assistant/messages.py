"""Notification and Live Activity text, in each supported language.

Home Assistant's translation files can't hold free-form messages, so the
text Ford Assistant sends to phones lives here. It's picked by Home
Assistant's own language (Settings -> System -> General), since a
notification isn't tied to one person's profile. Anything missing in a
language falls back to English.

To add a language: copy the "en" block, translate the values (keep every
``{placeholder}``), and add translations/<language>.json and the dashboard's
words (frontend/ford-assistant-panel.js, WORDS) too.
"""

from __future__ import annotations

from typing import Any

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # Doors
        "a_door": "A door",
        "and": "{first} and {last}",
        "door_title": "🚪 {name} door open",
        "door_open_for_one": "{doors} has been open for {minutes} minutes.",
        "door_open_for_many": "{doors} have been open for {minutes} minutes.",
        "door_is_open_one": "{doors} is open.",
        "door_is_open_many": "{doors} are open.",
        # Locking
        "autolock_title": "{name} locked",
        "autolock_message": (
            "Doors were left unlocked away from home, so Home Assistant locked them."
        ),
        "nightlock_failed_title": "🚪 {name} couldn't lock for the night",
        "nightlock_title": "{name} locked for the night",
        "nightlock_message": "It was still unlocked, so Home Assistant locked it.",
        # Remote start
        "temp_outside": "It's {temp}° outside. ",
        "warming_title": "{name} is warming up",
        "remote_started": "{temp}Remote started.",
        "work_title": "Start the {name}?",
        "work_message": "{temp}Tap Start to remote start before you head out.",
        "running": "Running",
        "running_header": "Remote start running",
        "degrees_outside": "{temp}° outside",
        "minutes_left": "{minutes} min left",
        # Alarm and windows
        "alarm_title": "🚨 {name} alarm",
        "alarm_message": "Alarm status: {state}",
        "windows_title": "{name} windows are open",
        "rain_message": "Rain is expected in the next few hours.",
        # Fuel, oil, warning lights
        "fuel_title": "⛽ {name} fuel is low",
        "battery_low_title": "🔋 {name} battery is low",
        "level_left": "{level}% left{extra}.",
        "about_range": " (about {range} range)",
        "oil_title": "🛢️ {name} oil change due",
        "oil_message": "Oil life is at {oil}%.",
        "oil_todo": "Oil change – {name}",
        "warning_title": "⚠️ {name} warning light",
        "warning_message": "A dashboard warning light is on.",
        # Garage
        "garage_open_title": "Garage opened for the {name}",
        "garage_open_message": (
            "Ford Assistant opened the garage because the {name} arrived home."
        ),
        "garage_open_log": "opened the garage because the {name} arrived home",
        "garage_closed_title": "Garage closed",
        "garage_closed_message": "The {name} is parked, so the garage door was closed.",
        # Charging
        "battery_text": "Battery is at {soc}%{extra}.",
        "plugin_title": "🔌 Plug in the {name}?",
        "charge_stopped_title": "⚠️ {name} charging stopped",
        "charger_not_detected": "The charger wasn't detected.",
        "charger_fault": "The charger reported a fault.",
        "charged_title": "🔋 {name} finished charging",
        "charged_message": "Charging is complete.",
        # Notification buttons
        "action_lock": "Lock",
        "action_honk": "Honk & Flash",
        "action_start": "Start",
        "action_stop": "Stop",
        "action_extend": "Extend",
        "action_open": "Open",
        "extended": "{name} remote start extended",
        "command_sent": "{command} sent to {name}",
        # 12V battery and tires
        "battery_12v_title": "🔋 {name} 12V battery low",
        "battery_12v_message": "{level}%{extra}.",
        "volts": " ({volts} V)",
        "tires_title": "🛞 {name} tire pressure",
        "tire_frontLeft": "Front left",
        "tire_frontRight": "Front right",
        "tire_rearLeft": "Rear left",
        "tire_rearRight": "Rear right",
        "garage_close_log": "closed the garage because the {name} is parked",
        # Vehicle status Live Activity
        "status_alarm": "Alarm!",
        "status_running": "Running",
        "status_driving": "Driving",
        "status_door_open": "Door open",
        "status_unlocked": "Unlocked",
        "status_locked": "Locked",
        "status_parked": "Parked",
        "part_alarm": "🚨 Alarm: {state}",
        "part_doors_open": "🚪 {doors} open",
        "part_door_open": "🚪 Door open",
        "part_windows_open": "🪟 Windows open",
        "part_locked": "🔒 Locked",
        "part_unlocked": "🔓 Unlocked",
        "part_charging": "⚡ Charging",
        "part_plugged_in": "🔌 Plugged in",
        "part_home": "🏠 Home",
        "away": "Away",
        # Door names the Ford integration reports (others are spelled out)
        "door_hood": "Hood",
        "door_tailgate": "Tailgate",
        "door_innerTailgate": "Inner tailgate",
        "door_driverFront": "Driver front",
        "door_passengerFront": "Passenger front",
        "door_driverRear": "Driver rear",
        "door_passengerRear": "Passenger rear",
    },
    "fr": {
        "a_door": "Une porte",
        "and": "{first} et {last}",
        "door_title": "🚪 {name} : porte ouverte",
        "door_open_for_one": "{doors} est ouverte depuis {minutes} minutes.",
        "door_open_for_many": "{doors} sont ouvertes depuis {minutes} minutes.",
        "door_is_open_one": "{doors} est ouverte.",
        "door_is_open_many": "{doors} sont ouvertes.",
        "autolock_title": "{name} verrouillé",
        "autolock_message": (
            "Les portes étaient restées déverrouillées loin de la maison, "
            "Home Assistant les a donc verrouillées."
        ),
        "nightlock_failed_title": "🚪 {name} n'a pas pu être verrouillé pour la nuit",
        "nightlock_title": "{name} verrouillé pour la nuit",
        "nightlock_message": (
            "Il était encore déverrouillé, Home Assistant l'a donc verrouillé."
        ),
        "temp_outside": "Il fait {temp}° dehors. ",
        "warming_title": "{name} se réchauffe",
        "remote_started": "{temp}Démarrage à distance effectué.",
        "work_title": "Démarrer {name} ?",
        "work_message": (
            "{temp}Touchez Démarrer pour le démarrer à distance avant de partir."
        ),
        "running": "En marche",
        "running_header": "Démarrage à distance en cours",
        "degrees_outside": "{temp}° dehors",
        "minutes_left": "{minutes} min restantes",
        "alarm_title": "🚨 Alarme {name}",
        "alarm_message": "État de l'alarme : {state}",
        "windows_title": "Les fenêtres de {name} sont ouvertes",
        "rain_message": "De la pluie est prévue dans les prochaines heures.",
        "fuel_title": "⛽ {name} : carburant bas",
        "battery_low_title": "🔋 {name} : batterie faible",
        "level_left": "{level} % restant{extra}.",
        "about_range": " (environ {range} d'autonomie)",
        "oil_title": "🛢️ {name} : vidange à faire",
        "oil_message": "Durée de vie de l'huile : {oil} %.",
        "oil_todo": "Vidange – {name}",
        "warning_title": "⚠️ {name} : voyant d'alerte",
        "warning_message": "Un voyant du tableau de bord est allumé.",
        "garage_open_title": "Garage ouvert pour {name}",
        "garage_open_message": (
            "Ford Assistant a ouvert le garage car {name} est arrivé à la maison."
        ),
        "garage_open_log": "a ouvert le garage car {name} est arrivé à la maison",
        "garage_closed_title": "Garage fermé",
        "garage_closed_message": (
            "{name} est garé, la porte du garage a donc été fermée."
        ),
        "battery_text": "Batterie à {soc} %{extra}.",
        "plugin_title": "🔌 Brancher {name} ?",
        "charge_stopped_title": "⚠️ {name} : recharge interrompue",
        "charger_not_detected": "La borne n'a pas été détectée.",
        "charger_fault": "La borne a signalé un problème.",
        "charged_title": "🔋 {name} : recharge terminée",
        "charged_message": "La recharge est terminée.",
        "action_lock": "Verrouiller",
        "action_honk": "Klaxon et feux",
        "action_start": "Démarrer",
        "action_stop": "Arrêter",
        "action_extend": "Prolonger",
        "action_open": "Ouvrir",
        "extended": "Démarrage à distance de {name} prolongé",
        "command_sent": "{command} : envoyé à {name}",
        "battery_12v_title": "🔋 {name} : batterie 12 V faible",
        "battery_12v_message": "{level} %{extra}.",
        "volts": " ({volts} V)",
        "tires_title": "🛞 {name} : pression des pneus",
        "tire_frontLeft": "Avant gauche",
        "tire_frontRight": "Avant droit",
        "tire_rearLeft": "Arrière gauche",
        "tire_rearRight": "Arrière droit",
        "garage_close_log": "a fermé le garage car {name} est garé",
        "status_alarm": "Alarme !",
        "status_running": "En marche",
        "status_driving": "En route",
        "status_door_open": "Porte ouverte",
        "status_unlocked": "Déverrouillé",
        "status_locked": "Verrouillé",
        "status_parked": "Garé",
        "part_alarm": "🚨 Alarme : {state}",
        "part_doors_open": "🚪 Ouvert : {doors}",
        "part_door_open": "🚪 Porte ouverte",
        "part_windows_open": "🪟 Fenêtres ouvertes",
        "part_locked": "🔒 Verrouillé",
        "part_unlocked": "🔓 Déverrouillé",
        "part_charging": "⚡ En charge",
        "part_plugged_in": "🔌 Branché",
        "part_home": "🏠 Maison",
        "away": "Absent",
        "door_hood": "Capot",
        "door_tailgate": "Hayon",
        "door_innerTailgate": "Hayon intérieur",
        "door_driverFront": "Avant conducteur",
        "door_passengerFront": "Avant passager",
        "door_driverRear": "Arrière conducteur",
        "door_passengerRear": "Arrière passager",
    },
}


def language_of(code: str | None) -> str:
    """The supported language for a Home Assistant language code (fr-CA -> fr)."""
    base = (code or "en").split("-")[0].split("_")[0].lower()
    return base if base in MESSAGES else "en"


def text(language: str | None, key: str, **values: Any) -> str:
    """A message in that language (English when it isn't translated)."""
    lang = language_of(language)
    template = MESSAGES[lang].get(key) or MESSAGES["en"][key]
    return template.format(**values)


def door_name(language: str | None, key: str, fallback: str) -> str:
    """A door's name, or ``fallback`` (the spelled-out key) if there isn't one."""
    lang = language_of(language)
    return (
        MESSAGES[lang].get(f"door_{key}")
        or MESSAGES["en"].get(f"door_{key}")
        or fallback
    )
