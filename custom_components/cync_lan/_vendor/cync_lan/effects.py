"""Run-mode effects on dynamic-effects lights: the layouts and light shows
saved in the Cync app, and what the status mode byte says is showing.

Pure functions, no I/O, and no import of cync_lan.const: Home Assistant
imports this module before the library's environment is configured.
Evidence: docs/cafe_lights_findings.md (captures on Cafe Lights, type 76).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Optional

__all__ = [
    "RunMode",
    "SavedEffect",
    "effect_from_status",
    "saved_effects_from_config",
    "saved_effects_from_properties",
    "saved_effects_to_config",
]


class RunMode(IntEnum):
    """modeCode of the light-run-mode command (op 0xE2, sub 0x07)."""

    STATIC = 0x00
    LIGHT_SHOW = 0x01
    MUSIC_SHOW = 0x02
    REVEAL = 0x03
    MULTI_COLOR = 0x04


@dataclass(frozen=True)
class SavedEffect:
    """A layout (MULTI_COLOR) or light show (LIGHT_SHOW) saved in the Cync
    app. `index` is its slot on the device, the index the run-mode command
    plays."""

    mode: RunMode
    index: int
    name: str


# Cloud home "properties" list -> the run mode that plays its entries.
_CLOUD_LISTS = (
    ("multiColorSchemes", RunMode.MULTI_COLOR),
    ("lightShows", RunMode.LIGHT_SHOW),
)
_CONFIG_KINDS = {RunMode.MULTI_COLOR: "layout", RunMode.LIGHT_SHOW: "light_show"}
_KIND_MODES = {kind: mode for mode, kind in _CONFIG_KINDS.items()}


def _slot(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if isinstance(value, int) and 1 <= value <= 255:
        return value
    return None


def _effect(mode: RunMode, entry: Any) -> Optional[SavedEffect]:
    if not isinstance(entry, Mapping):
        return None
    index = _slot(entry.get("index"))
    name = entry.get("name")
    if index is None or not isinstance(name, str) or not name.strip():
        return None
    return SavedEffect(mode, index, name.strip())


def _unique_sorted(effects: Iterable[SavedEffect]) -> list[SavedEffect]:
    seen: dict[tuple[RunMode, int], SavedEffect] = {}
    for effect in effects:
        seen.setdefault((effect.mode, effect.index), effect)
    return [seen[key] for key in sorted(seen)]


def saved_effects_from_properties(properties: Mapping[str, Any]) -> list[SavedEffect]:
    """Saved layouts and light shows from a cloud home record's `properties`
    (multiColorSchemes, lightShows): one per slot, sorted by mode then slot.
    Entries without a usable slot (1-255) or name are skipped; the first
    entry for a slot wins."""
    found: list[SavedEffect] = []
    for key, mode in _CLOUD_LISTS:
        entries = properties.get(key)
        if isinstance(entries, list):
            for entry in entries:
                effect = _effect(mode, entry)
                if effect is not None:
                    found.append(effect)
    return _unique_sorted(found)


def saved_effects_to_config(effects: Iterable[SavedEffect]) -> list[dict[str, Any]]:
    """The cync_mesh.yaml form: [{"kind": "layout"|"light_show", "index", "name"}]."""
    return [
        {"kind": _CONFIG_KINDS[effect.mode], "index": effect.index, "name": effect.name}
        for effect in effects
    ]


def saved_effects_from_config(entries: Any) -> list[SavedEffect]:
    """Inverse of saved_effects_to_config(); bad entries are skipped."""
    if not isinstance(entries, list):
        return []
    found: list[SavedEffect] = []
    for entry in entries:
        if isinstance(entry, Mapping) and entry.get("kind") in _KIND_MODES:
            effect = _effect(_KIND_MODES[entry["kind"]], entry)
            if effect is not None:
                found.append(effect)
    return _unique_sorted(found)


def effect_from_status(mode_byte: Optional[int]) -> Optional[tuple[RunMode, int]]:
    """(mode, index) of the effect a status mode byte reports, or None.

    The byte after brightness in the status record (EntityState.temperature):
    0-100 is a white temperature and 254 means RGB, neither is an effect.
    Captured on Cafe Lights: light shows 1-32 are 0x80 | (index - 1), music
    shows 1-8 are 0xA0 | (index - 1), Cyber (light show 67) is 0xE3, and
    layout 3 showed 0xC2. Inferred from those: layouts are 0xC0 | (index - 1)
    and light shows 65 and 66 are 0xE1 and 0xE2.
    """
    if mode_byte is None:
        return None
    if 0x80 <= mode_byte <= 0x9F:
        return (RunMode.LIGHT_SHOW, mode_byte - 0x7F)
    if 0xA0 <= mode_byte <= 0xBF:
        return (RunMode.MUSIC_SHOW, mode_byte - 0x9F)
    if 0xC0 <= mode_byte <= 0xDF:
        return (RunMode.MULTI_COLOR, mode_byte - 0xBF)
    if 0xE1 <= mode_byte <= 0xE3:
        return (RunMode.LIGHT_SHOW, mode_byte - 0xE0 + 64)
    return None
