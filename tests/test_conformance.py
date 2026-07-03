"""Conformance harness: the cross-language contract.

Any backend port (Julia, C#, R, …) is *certified* when its message builders reproduce
these golden fixtures. This test proves the Python reference stays in sync with them; a
port re-implements the same assertions in its own test runner.
"""

import base64
import json
from pathlib import Path

import pytest

from cositos import build_comm_open, build_custom, build_update

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _enc(buffers):
    return [base64.b64encode(bytes(b)).decode() for b in buffers]


def test_comm_open_matches_fixture():
    fx = _load("comm_open")
    state = {"_esm": "export default { render() {} }", "value": 0}
    data, buffers, metadata = build_comm_open(state)
    assert data == fx["data"]
    assert _enc(buffers) == fx["buffers_b64"]
    assert metadata == fx["metadata"]


def test_update_matches_fixture():
    fx = _load("update")
    data, buffers = build_update({"value": 42})
    assert data == fx["data"]
    assert _enc(buffers) == fx["buffers_b64"]


def test_update_nested_buffer_matches_fixture():
    fx = _load("update_nested_buffer")
    data, buffers = build_update({"img": {"bytes": b"PNGDATA"}, "shape": [1, 1]})
    assert data == fx["data"]
    assert _enc(buffers) == fx["buffers_b64"]


def test_custom_matches_fixture():
    fx = _load("custom")
    assert build_custom({"event": "click", "n": 3}) == fx["data"]


@pytest.mark.parametrize("name", ["comm_open", "update", "update_nested_buffer", "custom"])
def test_fixture_is_valid_json(name):
    assert isinstance(_load(name), dict)
