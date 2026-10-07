"""The effect names a light offers: the library's built-in run modes plus
the layouts and light shows saved in the Cync app (from the cloud export),
and the reverse lookup from what the light reports it is showing."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cync_lan.effects import RunMode, SavedEffect


@dataclass(frozen=True)
class EffectTarget:
    """How to play one effect name."""

    mode: int
    index: int
    # The LIGHT_RUN_MODE_EFFECTS key of a built-in, played with
    # set_light_effect() as before; None for a saved layout or show, played
    # by slot with play_effect().
    builtin: str | None = None


class EffectCatalog:
    """Effect names in list order: built-ins first, then saved layouts and
    shows. A saved name that clashes with one already taken (ignoring case),
    or with a reserved name such as HA's "off", gets its kind and slot
    appended, e.g. "Candle (show 12)". Reserved names are not playable here;
    the caller handles them."""

    def __init__(
        self,
        builtins: Mapping[str, tuple[int, int, int]],
        saved: Iterable[SavedEffect] = (),
        reserved: Iterable[str] = (),
    ) -> None:
        self._taken: set[str] = {name.casefold() for name in reserved}
        self._targets: dict[str, EffectTarget] = {}
        self._folded: dict[str, EffectTarget] = {}
        self._names: dict[tuple[int, int], str] = {}
        for name, (mode, index, _nonce) in builtins.items():
            self._add(name, EffectTarget(mode, index, builtin=name))
            # Static and Reveal (index 0) never show up in the status byte.
            if index:
                self._names.setdefault((mode, index), name)
        for effect in saved:
            name = effect.name
            if name.casefold() in self._taken:
                kind = "layout" if effect.mode == RunMode.MULTI_COLOR else "show"
                name = f"{effect.name} ({kind} {effect.index})"
            self._add(name, EffectTarget(int(effect.mode), effect.index))
            self._names[(int(effect.mode), effect.index)] = name

    def _add(self, name: str, target: EffectTarget) -> None:
        self._targets[name] = target
        self._folded.setdefault(name.casefold(), target)
        self._taken.add(name.casefold())

    @property
    def names(self) -> list[str]:
        return list(self._targets)

    def target(self, name: str) -> EffectTarget | None:
        return self._targets.get(name) or self._folded.get(name.casefold())

    def name_for(self, mode: int, index: int) -> str | None:
        return self._names.get((mode, index))
