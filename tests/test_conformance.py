"""Conformance harness: the cross-language contract.

Any backend port (Julia, C#, R, …) is *certified* when its message builders reproduce
these golden fixtures. This test proves the Python reference stays in sync with them; a
port re-implements the same assertions in its own test runner.
"""

import array
import base64
import json
from pathlib import Path

import pytest

from cositos import build_comm_open, build_custom, build_update
from cositos.serialize import dump_document, load_document

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


def _widget_state_entries():
    # A composed UI: a container referencing a child that carries a float32 array buffer.
    return [
        (
            "box",
            {
                "_esm": "export default { render({model, el}) { /* VBox */ } }",
                "children": ["IPY_MODEL_plot"],
            },
        ),
        (
            "plot",
            {
                "_esm": "export default { render({model, el}) { /* float32 plot */ } }",
                "shape": [3],
                "dtype": "float32",
                "data": memoryview(array.array("f", [1.5, 2.5, -3.0])),
            },
        ),
    ]


def _raw(b):
    return memoryview(b).cast("B").tobytes()


def test_widget_state_dump_matches_fixture():
    # The Python reference reproduces the golden document byte-for-byte (base64 buffers).
    assert dump_document(_widget_state_entries()) == _load("widget-state")


def test_widget_state_load_reconstructs_entries():
    loaded = load_document(_load("widget-state"))
    expected = _widget_state_entries()
    assert [mid for mid, _ in loaded] == [mid for mid, _ in expected]
    # Composition ref survives; float32 buffer round-trips by raw bytes.
    by_id = dict(loaded)
    assert by_id["box"]["children"] == ["IPY_MODEL_plot"]
    assert _raw(by_id["plot"]["data"]) == _raw(memoryview(array.array("f", [1.5, 2.5, -3.0])))
