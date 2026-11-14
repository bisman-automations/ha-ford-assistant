"""Notification text in each language (messages.py) and the translations."""

import json
from pathlib import Path
import string

from custom_components.ford_assistant import messages

COMPONENT = Path(__file__).parent.parent / "custom_components" / "ford_assistant"


def _fields(template: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def _keys(data: dict, prefix: str = "") -> set[str]:
    keys = set()
    for key, value in data.items():
        if isinstance(value, dict):
            keys |= _keys(value, f"{prefix}{key}.")
        else:
            keys.add(prefix + key)
    return keys


def test_every_language_has_every_message_with_its_placeholders():
    english = messages.MESSAGES["en"]
    for lang, words in messages.MESSAGES.items():
        assert set(words) == set(english), lang
        for key, template in words.items():
            assert _fields(template) == _fields(english[key]), (lang, key)


def test_text_follows_home_assistants_language():
    assert messages.text("fr", "a_door") == "Une porte"
    assert messages.text("fr-CA", "a_door") == "Une porte"
    assert messages.text("en-GB", "a_door") == "A door"
    # A language without messages, or none at all: English.
    assert messages.text("de", "a_door") == "A door"
    assert messages.text(None, "a_door") == "A door"
    assert messages.text("fr", "door_title", name="F-150") == "🚪 F-150 : porte ouverte"
    assert messages.door_name("fr", "driverFront", "Driver front") == "Avant conducteur"
    assert messages.door_name("fr", "frunk", "Frunk") == "Frunk"


def test_every_translation_has_every_key():
    english = _keys(json.loads((COMPONENT / "translations" / "en.json").read_text()))
    for path in sorted((COMPONENT / "translations").glob("*.json")):
        if path.name == "en.json":
            continue
        translated = _keys(json.loads(path.read_text()))
        assert translated == english, path.name
