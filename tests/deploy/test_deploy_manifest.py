"""The deploy manifest must never make HA fetch cync-lan from the internet."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMP = ROOT / "custom_components" / "cync_lan"
MANIFEST = json.loads((COMP / "manifest.json").read_text())
VENDORED = json.loads((COMP / "_vendor" / "VENDORED.json").read_text())


def test_no_url_and_no_cync_lan_requirement() -> None:
    for req in MANIFEST["requirements"]:
        assert "://" not in req and " @ " not in req and not req.startswith("git+")
        assert not req.lower().replace("_", "-").startswith("cync-lan")


def test_lists_every_bundled_library_dependency() -> None:
    for dep in VENDORED["lib_requirements"]:
        assert dep in MANIFEST["requirements"]


def test_version_matches_release() -> None:
    assert MANIFEST["version"] == VENDORED["release"]
    assert re.fullmatch(r"\d+\.\d+\.\d+-tp\.\d+", MANIFEST["version"])
