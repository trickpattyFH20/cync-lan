"""The deploy branch must run the bundled cync_lan, not a PyPI install."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "custom_components" / "cync_lan" / "_vendor"


def test_integration_import_loads_bundled_library() -> None:
    code = (
        "import json, importlib.metadata as m;"
        "import custom_components.cync_lan;"
        "import cync_lan;"
        "print(json.dumps({'file': cync_lan.__file__,"
        " 'version': m.version('cync-lan')}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    data = json.loads(out.strip().splitlines()[-1])
    assert Path(data["file"]).resolve().is_relative_to(VENDOR.resolve())
    vendored = json.loads((VENDOR / "VENDORED.json").read_text())
    assert data["version"] == vendored["bundled_version"]


def test_check_bundled_library_true_for_vendor(caplog: pytest.LogCaptureFixture) -> None:
    import custom_components.cync_lan as integration

    caplog.set_level(logging.INFO)
    import cync_lan

    if not Path(cync_lan.__file__).resolve().is_relative_to(VENDOR.resolve()):
        pytest.skip("this test process imported a non-bundled cync_lan first")
    assert integration._check_bundled_library() is True
    assert "Using bundled cync_lan" in caplog.text


def test_check_bundled_library_warns_otherwise(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    import custom_components.cync_lan as integration
    import cync_lan

    monkeypatch.setattr(
        cync_lan, "__file__", "/usr/local/lib/python3.14/site-packages/cync_lan/__init__.py"
    )
    assert integration._check_bundled_library() is False
    assert "not the bundled copy" in caplog.text
    assert "restart Home Assistant" in caplog.text
