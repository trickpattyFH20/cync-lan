"""Tests for scripts/bundle_lib.py (deploy branch only)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "bundle_lib", ROOT / "scripts" / "bundle_lib.py"
)
assert _spec and _spec.loader
bundle_lib = importlib.util.module_from_spec(_spec)
sys.modules["bundle_lib"] = bundle_lib
_spec.loader.exec_module(bundle_lib)

GIT_ID = ["-c", "user.email=test@example.com", "-c", "user.name=test"]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *GIT_ID, *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def fake_lib(tmp_path: Path) -> Path:
    lib = tmp_path / "lib"
    (lib / "src" / "cync_lan" / "packet").mkdir(parents=True)
    (lib / "src" / "cync_lan" / "__init__.py").write_text("X = 1\n")
    (lib / "src" / "cync_lan" / "py.typed").write_text("")
    (lib / "src" / "cync_lan" / "packet" / "builder.py").write_text("Y = 2\n")
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "cync-lan"\nversion = "9.9.9"\n'
        'dependencies = ["tzlocal>=5.3.1", "pyyaml>=6.0.2"]\n'
    )
    _git(lib, "init", "-q", "-b", "main")
    _git(lib, "add", ".")
    _git(lib, "commit", "-q", "-m", "init")
    return lib


@pytest.fixture
def fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "integration"
    comp = root / "custom_components" / "cync_lan"
    comp.mkdir(parents=True)
    (comp / "manifest.json").write_text(
        json.dumps(
            {
                "domain": "cync_lan",
                "requirements": ["cync-lan>=0.16.1", "pyyaml>=6.0.2"],
                "version": "2.15.0",
            },
            indent=2,
        )
        + "\n"
    )
    return root


def _vendor(root: Path) -> Path:
    return root / "custom_components" / "cync_lan" / "_vendor"


def test_copies_library_at_ref(fake_lib: Path, fake_root: Path) -> None:
    info = bundle_lib.bundle(fake_lib, "main", fake_root, "2.15.0-tp.1")
    vendor = _vendor(fake_root)
    assert (vendor / "cync_lan" / "__init__.py").read_text() == "X = 1\n"
    assert (vendor / "cync_lan" / "packet" / "builder.py").read_text() == "Y = 2\n"
    assert (vendor / "cync_lan" / "py.typed").exists()
    commit = _git(fake_lib, "rev-parse", "HEAD")
    assert info.lib_commit == commit
    assert info.bundled_version == f"9.9.9+tp.{commit[:7]}"


def test_vendored_json_and_readme(fake_lib: Path, fake_root: Path) -> None:
    info = bundle_lib.bundle(fake_lib, "main", fake_root, "2.15.0-tp.1")
    data = json.loads((_vendor(fake_root) / "VENDORED.json").read_text())
    assert data["commit"] == info.lib_commit
    assert data["ref"] == "main"
    assert data["lib_version"] == "9.9.9"
    assert data["bundled_version"] == info.bundled_version
    assert data["release"] == "2.15.0-tp.1"
    assert data["lib_requirements"] == ["tzlocal>=5.3.1", "pyyaml>=6.0.2"]
    assert "Do not edit" in (_vendor(fake_root) / "README.md").read_text()


def test_metadata_reports_bundled_version(fake_lib: Path, fake_root: Path) -> None:
    info = bundle_lib.bundle(fake_lib, "main", fake_root, "2.15.0-tp.1")
    code = (
        "import sys, importlib.metadata as m;"
        f"sys.path.insert(0, {str(_vendor(fake_root))!r});"
        "print(m.version('cync-lan'))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    ).stdout.strip()
    assert out == info.bundled_version


def test_manifest_requirements_and_version(fake_lib: Path, fake_root: Path) -> None:
    bundle_lib.bundle(fake_lib, "main", fake_root, "2.15.0-tp.1")
    manifest = json.loads(
        (fake_root / "custom_components" / "cync_lan" / "manifest.json").read_text()
    )
    assert manifest["requirements"] == ["pyyaml>=6.0.2", "tzlocal>=5.3.1"]
    assert manifest["version"] == "2.15.0-tp.1"
    assert manifest["domain"] == "cync_lan"


def test_removes_stale_vendor_files(fake_lib: Path, fake_root: Path) -> None:
    stale_mod = _vendor(fake_root) / "cync_lan" / "old_module.py"
    stale_dist = _vendor(fake_root) / "cync_lan-0.0.1.dist-info"
    stale_mod.parent.mkdir(parents=True)
    stale_mod.write_text("OLD = True\n")
    stale_dist.mkdir()
    bundle_lib.bundle(fake_lib, "main", fake_root, "2.15.0-tp.1")
    assert not stale_mod.exists()
    assert not stale_dist.exists()


def test_refuses_dirty_checkout(fake_lib: Path, fake_root: Path) -> None:
    (fake_lib / "src" / "cync_lan" / "__init__.py").write_text("X = 'dirty'\n")
    with pytest.raises(bundle_lib.BundleError, match="uncommitted"):
        bundle_lib.bundle(fake_lib, "main", fake_root, "2.15.0-tp.1")
    assert not _vendor(fake_root).exists()


def test_refuses_unknown_ref(fake_lib: Path, fake_root: Path) -> None:
    with pytest.raises(bundle_lib.BundleError, match="unknown ref"):
        bundle_lib.bundle(fake_lib, "no-such-branch", fake_root, "2.15.0-tp.1")
    assert not _vendor(fake_root).exists()


def test_merge_drops_cync_lan_and_lib_specifier_wins() -> None:
    merged = bundle_lib.merge_requirements(
        ["cync-lan>=0.16.1", "PyYAML>=6.0.0", "zeroconf>=0.1"],
        ["pyyaml>=6.0.2", "aiohttp>=3.10.8"],
    )
    assert merged == ["aiohttp>=3.10.8", "pyyaml>=6.0.2", "zeroconf>=0.1"]


@pytest.mark.parametrize(
    "bad",
    [
        "foo @ git+https://example.com/foo.git",
        "git+https://example.com/foo.git#egg=foo",
        "foo @ https://example.com/foo.whl",
    ],
)
def test_merge_rejects_url_requirements(bad: str) -> None:
    with pytest.raises(bundle_lib.BundleError, match="URL requirement"):
        bundle_lib.merge_requirements(["cync-lan>=1"], [bad])
