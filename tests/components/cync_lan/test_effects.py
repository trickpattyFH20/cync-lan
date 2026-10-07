"""Tests for the effect catalog (built-in run modes + app-saved effects)."""

from __future__ import annotations

from cync_lan.effects import RunMode, SavedEffect

from custom_components.cync_lan.effects import EffectCatalog, EffectTarget

BUILTINS = {
    "candle": (0x01, 1, 0xF1),
    "static": (0x00, 0, 0x00),
    "multicolor": (0x04, 1, 0x00),
}
SAVED = [
    SavedEffect(RunMode.LIGHT_SHOW, 10, "Holly"),
    SavedEffect(RunMode.MULTI_COLOR, 3, "Spooky"),
]


def test_names_list_builtins_then_saved() -> None:
    assert EffectCatalog(BUILTINS, SAVED).names == [
        "candle",
        "static",
        "multicolor",
        "Holly",
        "Spooky",
    ]


def test_targets_say_how_to_play() -> None:
    catalog = EffectCatalog(BUILTINS, SAVED)
    assert catalog.target("candle") == EffectTarget(1, 1, builtin="candle")
    assert catalog.target("Holly") == EffectTarget(1, 10)
    assert catalog.target("Spooky") == EffectTarget(4, 3)
    assert catalog.target("holly") == EffectTarget(1, 10)  # case-insensitive fallback
    assert catalog.target("nope") is None


def test_name_for_maps_a_reported_slot_back_to_its_name() -> None:
    catalog = EffectCatalog(BUILTINS, SAVED)
    assert catalog.name_for(1, 1) == "candle"
    assert catalog.name_for(1, 10) == "Holly"
    assert catalog.name_for(4, 3) == "Spooky"
    assert catalog.name_for(4, 1) == "multicolor"
    assert catalog.name_for(1, 24) is None  # saved in the app after the last export
    assert catalog.name_for(0, 0) is None  # Static is never reported


def test_clashing_names_get_kind_and_slot() -> None:
    saved = [
        SavedEffect(RunMode.LIGHT_SHOW, 12, "Candle"),
        SavedEffect(RunMode.LIGHT_SHOW, 13, "Xmas"),
        SavedEffect(RunMode.MULTI_COLOR, 4, "Xmas"),
    ]
    catalog = EffectCatalog(BUILTINS, saved)
    assert catalog.names[-3:] == ["Candle (show 12)", "Xmas", "Xmas (layout 4)"]
    assert catalog.target("Candle (show 12)") == EffectTarget(1, 12)
    assert catalog.target("candle") == EffectTarget(1, 1, builtin="candle")
    assert catalog.name_for(4, 4) == "Xmas (layout 4)"


def test_no_saved_effects_is_just_the_builtins() -> None:
    assert EffectCatalog(BUILTINS).names == ["candle", "static", "multicolor"]
