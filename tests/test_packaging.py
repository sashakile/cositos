"""Packaging regression tests for the cositos wheel.

Guards the wheel-inclusion contract (cositos-w9o): ``cositos.contrib.controls`` must
resolve its controls catalog from *inside* the installed wheel (as package data via
``importlib.resources``), not from a repository-relative filesystem path that only
exists in an editable/source checkout. A fresh, non-editable wheel install has no
``fixtures/`` directory, so the module must keep working from within the archive.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The catalog lives with the module as package data inside the wheel.
CATALOG_IN_WHEEL = "cositos/contrib/data/controls-catalog.json"


def _build_wheel(tmp_path: Path) -> Path:
    """Build a wheel into ``tmp_path`` and return the wheel file path."""
    build_dir = tmp_path / "dist"
    build_dir.mkdir()
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(build_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(build_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got: {wheels}"
    return wheels[0]


@pytest.fixture()
def wheel(tmp_path: Path) -> Path:
    return _build_wheel(tmp_path)


def test_wheel_archive_contains_the_controls_catalog(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    assert CATALOG_IN_WHEEL in names, (
        f"wheel missing {CATALOG_IN_WHEEL}; controls module would fail to import "
        "outside an editable/source install"
    )


def test_import_controls_from_isolated_wheel_install(wheel: Path, tmp_path: Path) -> None:
    """A non-editable wheel install can import ``cositos.contrib.controls``.

    Install the wheel into an isolated ``--target`` dir (with no repo ``src/`` on
    ``sys.path``) and import the module; the catalog must resolve from inside the
    wheel, not from the repository's ``fixtures/`` directory.
    """
    target = tmp_path / "site"
    subprocess.run(
        ["uv", "pip", "install", "--target", str(target), str(wheel)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )

    # Run in a subprocess so the isolated target is the ONLY place the module can come
    # from: never pollute the test process's sys.path with the repo's editable src.
    target_repr = repr(str(target))
    probe = (
        f"import sys; sys.path.insert(0, {target_repr});"
        "import cositos.contrib.controls as c;"
        "entries = c.int_slider(value=5);"
        "_, state = entries[0];"
        "assert state['value'] == 5, state;"
        "print(state['_model_name'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "IntSliderModel"
