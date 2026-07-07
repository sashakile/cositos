"""Unit tests for the ``mise run e2e-all`` orchestrator (scripts/e2e_all.py).

The orchestrator runs every per-language e2e example in isolation and classifies each
as OK / SKIP / FAIL. These tests inject fake ``which`` / ``task_exists`` / ``run_task``
callables so the classification and exit-code logic can be verified without any real
language runtime installed — the acceptance criteria of cositos-1wi.1:

  * a missing runtime => SKIP(<lang>: no <runtime>), never FAIL;
  * a non-zero (or non-"OK") per-language run => FAIL, in isolation from the others;
  * exit code is non-zero iff at least one language FAILed (SKIP is not failure).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("e2e_all", ROOT / "scripts" / "e2e_all.py")
assert _spec and _spec.loader
e2e_all = importlib.util.module_from_spec(_spec)
sys.modules["e2e_all"] = e2e_all
_spec.loader.exec_module(e2e_all)

Language = e2e_all.Language
Outcome = e2e_all.Outcome


def _lang(name: str) -> Language:
    return Language(name=name, runtime=f"{name}-rt", task=f"e2e-{name}")


def test_ok_when_runtime_present_task_exists_and_output_ok():
    # ARRANGE: one language whose runtime is present, task defined, run prints "OK <lang>".
    lang = _lang("python")
    which = lambda rt: f"/usr/bin/{rt}"  # noqa: E731 - all runtimes present
    task_exists = lambda t: True  # noqa: E731
    run_task = lambda t: (0, "OK python\n")  # noqa: E731

    # ACT
    results, exit_code = e2e_all.orchestrate(
        [lang], which=which, task_exists=task_exists, run_task=run_task
    )

    # ASSERT
    assert exit_code == 0
    assert results[0].outcome is Outcome.OK


def test_skip_when_runtime_missing():
    lang = _lang("julia")
    which = lambda rt: None  # noqa: E731 - runtime absent
    results, exit_code = e2e_all.orchestrate(
        [lang], which=which, task_exists=lambda t: True, run_task=lambda t: (0, "OK julia")
    )
    assert exit_code == 0  # SKIP is not failure
    assert results[0].outcome is Outcome.SKIP
    assert "no julia-rt" in results[0].detail


def test_skip_when_task_not_yet_implemented():
    lang = _lang("r")
    results, exit_code = e2e_all.orchestrate(
        [lang],
        which=lambda rt: f"/usr/bin/{rt}",
        task_exists=lambda t: False,  # per-language ticket not landed yet
        run_task=lambda t: (0, "unused"),
    )
    assert exit_code == 0
    assert results[0].outcome is Outcome.SKIP


def test_fail_on_nonzero_exit():
    lang = _lang("csharp")
    results, exit_code = e2e_all.orchestrate(
        [lang],
        which=lambda rt: f"/usr/bin/{rt}",
        task_exists=lambda t: True,
        run_task=lambda t: (1, "boom: state diverged"),
    )
    assert exit_code != 0
    assert results[0].outcome is Outcome.FAIL
    assert "boom" in results[0].detail


def test_fail_when_zero_exit_but_no_ok_marker():
    # A program that exits 0 without printing the "OK <lang>" contract marker is a FAIL:
    # the marker is the contract's success signal, not the exit code alone.
    lang = _lang("clojure")
    results, exit_code = e2e_all.orchestrate(
        [lang],
        which=lambda rt: f"/usr/bin/{rt}",
        task_exists=lambda t: True,
        run_task=lambda t: (0, "did nothing useful"),
    )
    assert exit_code != 0
    assert results[0].outcome is Outcome.FAIL


def test_one_failure_does_not_mask_other_languages():
    # ARRANGE: python OK, julia FAIL, r SKIP (no runtime) — all reported independently.
    langs = [_lang("python"), _lang("julia"), _lang("r")]
    which = lambda rt: None if rt == "r-rt" else f"/usr/bin/{rt}"  # noqa: E731
    outputs = {"e2e-python": (0, "OK python"), "e2e-julia": (2, "diff!")}

    results, exit_code = e2e_all.orchestrate(
        langs,
        which=which,
        task_exists=lambda t: True,
        run_task=lambda t: outputs[t],
    )

    by_name = {r.language: r.outcome for r in results}
    assert by_name == {
        "python": Outcome.OK,
        "julia": Outcome.FAIL,
        "r": Outcome.SKIP,
    }
    assert exit_code != 0  # the julia FAIL drives the exit code


def test_summary_table_lists_every_language_and_outcome():
    results = [
        e2e_all.Result("python", Outcome.OK, ""),
        e2e_all.Result("julia", Outcome.SKIP, "no julia"),
        e2e_all.Result("r", Outcome.FAIL, "diverged"),
    ]
    table = e2e_all.format_summary(results)
    for token in ("python", "julia", "r", "OK", "SKIP", "FAIL"):
        assert token in table
