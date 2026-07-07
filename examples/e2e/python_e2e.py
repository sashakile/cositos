#!/usr/bin/env python3
"""Python reference implementation of the cross-language e2e contract (cositos-1wi.2).

This is the **oracle**: the canonical widget-state document the other language ports must
match (modulo JSON formatting). See ``examples/e2e/README.md`` for the full contract. The
program:

  1. builds the FIXED input (an anywidget counter, ``{_esm, value: 42}``) into a
     widget-state ``Document`` via :func:`cositos.dump_document`;
  2. asserts the round-trip law ``load(dump(x)) == x`` via :func:`cositos.load_document`;
  3. diffs the produced document against the pinned ``expected.json`` in this directory;
  4. prints ``OK python`` and exits 0 on success, or a readable diff and a non-zero exit
     on any divergence.

Run it with ``mise run e2e-python``.
"""

from __future__ import annotations

import difflib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from cositos import dump_document, load_document

HERE = Path(__file__).resolve().parent
EXPECTED_PATH = HERE / "expected.json"

# The FIXED input state the whole contract is pinned to (see README "The fixed input").
ESM = 'export default { render({ model, el }) { el.textContent = model.get("value"); } }'
MODEL_ID = "counter"
INPUT_STATE: dict[str, Any] = {"_esm": ESM, "value": 42}


def build_document() -> dict[str, Any]:
    """Serialize the fixed counter into a widget-state Document.

    A deep copy of the input is passed in because ``dump_document`` preserves buffer-free
    state by reference; copying keeps the returned document from aliasing the module
    constant, so callers can freely inspect or mutate it without corrupting the oracle.
    """
    return dump_document([(MODEL_ID, deepcopy(INPUT_STATE))])


def load_expected() -> dict[str, Any]:
    """The pinned golden document this port certifies against."""
    return json.loads(EXPECTED_PATH.read_text())


def round_trip_failures() -> list[str]:
    """Check ``load(dump(x)) == x``; return failure messages (empty means it holds)."""
    doc = build_document()
    loaded = load_document(doc)
    expected_entries = [(MODEL_ID, INPUT_STATE)]
    if loaded == expected_entries:
        return []
    return [f"round-trip law violated: load(dump(x)) = {loaded!r}, expected {expected_entries!r}"]


def _json_diff(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    if expected == actual:
        return []
    exp = json.dumps(expected, indent=2, sort_keys=True).splitlines()
    act = json.dumps(actual, indent=2, sort_keys=True).splitlines()
    diff = difflib.unified_diff(exp, act, fromfile="expected.json", tofile="produced", lineterm="")
    return ["produced document diverges from expected.json:", *diff]


def verify(expected: dict[str, Any]) -> list[str]:
    """Run the full contract; return a list of failure messages (empty means pass)."""
    return round_trip_failures() + _json_diff(expected, build_document())


def main() -> int:
    failures = verify(load_expected())
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("OK python")
    return 0


if __name__ == "__main__":
    sys.exit(main())
