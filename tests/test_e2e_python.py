"""Tests for the Python reference e2e example (examples/e2e/python_e2e.py).

The Python program is the *oracle* for the cross-language e2e contract (cositos-1wi.2):
the other language ports must byte-match its output (modulo JSON formatting). These tests
verify it satisfies the contract from examples/e2e/README.md — a passing run reports OK
and a diverging expected document is reported as a readable diff, not a crash.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "python_e2e", ROOT / "examples" / "e2e" / "python_e2e.py"
)
assert _spec and _spec.loader
python_e2e = importlib.util.module_from_spec(_spec)
sys.modules["python_e2e"] = python_e2e
_spec.loader.exec_module(python_e2e)


def test_build_document_matches_pinned_expected():
    # ARRANGE: the pinned golden document.
    expected = python_e2e.load_expected()
    # ACT: build the fixed counter document from the reference emitter.
    doc = python_e2e.build_document()
    # ASSERT: it equals the pinned expected value.
    assert doc == expected


def test_verify_passes_against_matching_expected():
    failures = python_e2e.verify(python_e2e.load_expected())
    assert failures == []


def test_verify_reports_readable_diff_on_divergence():
    # ARRANGE: a deliberately wrong expected document (value tampered).
    tampered = python_e2e.build_document()
    tampered["state"]["counter"]["state"]["value"] = 999
    # ACT
    failures = python_e2e.verify(tampered)
    # ASSERT: divergence is reported, and the message shows the offending values.
    assert failures
    joined = "\n".join(failures)
    assert "999" in joined or "42" in joined


def test_round_trip_law_holds():
    # load(dump(x)) == x for the fixed input, independent of the pinned file.
    assert python_e2e.round_trip_failures() == []


def test_main_exits_zero_and_prints_ok(capsys):
    rc = python_e2e.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK python" in out
