"""Tests for widget-state serialization foundation: types + base64 buffer codec."""

import array

from cositos.serialize import (
    Document,
    ModelEntry,
    decode_buffers_base64,
    dump_document,
    dump_model,
    encode_buffers_base64,
    load_document,
    load_model,
)


def _raw(b: object) -> bytes:
    return memoryview(b).cast("B").tobytes()  # type: ignore[arg-type]


def test_types_are_importable() -> None:
    # ModelEntry and Document are the named boundary types the round-trip law needs.
    entry: ModelEntry = ("m1", {"value": 1})
    doc: Document = {"version_major": 2, "version_minor": 0, "state": {}}
    assert entry[0] == "m1"
    assert doc["version_major"] == 2


def test_encode_produces_v2_buffer_records() -> None:
    stripped = {"a": 1}
    json_split = encode_buffers_base64((stripped, [["blob"]], [b"abc"]))
    result_stripped, entries = json_split
    assert result_stripped is stripped  # stripped passes through untouched
    assert entries == [{"path": ["blob"], "encoding": "base64", "data": "YWJj"}]


def test_round_trip_plain_bytes() -> None:
    split = ({"a": 1}, [["x", "data"], ["y", 0]], [b"hello", b"\x00\x01\x02"])
    stripped2, paths2, buffers2 = decode_buffers_base64(encode_buffers_base64(split))
    assert stripped2 == {"a": 1}
    assert paths2 == [["x", "data"], ["y", 0]]
    assert [_raw(b) for b in buffers2] == [b"hello", b"\x00\x01\x02"]


def test_round_trip_float32_array_by_raw_bytes() -> None:
    # A float32 memoryview must serialise by its raw bytes (ipywidgets _buffer_list_equal):
    # comparing memoryviews directly would wrongly fail on format/dtype.
    arr = array.array("f", [1.5, 2.5, -3.0])
    split = ({"shape": [3], "dtype": "float32"}, [["data"]], [memoryview(arr)])
    _, _, buffers2 = decode_buffers_base64(encode_buffers_base64(split))
    assert _raw(buffers2[0]) == _raw(memoryview(arr))


def test_no_buffers_round_trips() -> None:
    split = ({"a": 1, "b": [1, 2]}, [], [])
    stripped2, paths2, buffers2 = decode_buffers_base64(encode_buffers_base64(split))
    assert stripped2 == {"a": 1, "b": [1, 2]}
    assert paths2 == []
    assert buffers2 == []


def test_decode_rejects_unknown_encoding() -> None:
    bad = ({}, [{"path": ["x"], "encoding": "hex", "data": "6162"}])
    try:
        decode_buffers_base64(bad)
    except ValueError as e:
        assert "hex" in str(e)
    else:
        raise AssertionError("expected ValueError for unsupported encoding")


def test_dump_model_defaults_to_anywidget_identity() -> None:
    model_id, record = dump_model(("m1", {"value": 1}))
    assert model_id == "m1"
    assert record["model_name"] == "AnyModel"
    assert record["model_module"] == "anywidget"
    assert "model_module_version" in record
    assert record["state"] == {"value": 1}
    assert "buffers" not in record  # omitted when there are no binary values


def test_dump_model_respects_explicit_model_fields() -> None:
    state = {
        "value": 1,
        "_model_name": "MyModel",
        "_model_module": "my-pkg",
        "_model_module_version": "^1.2.3",
    }
    _, record = dump_model(("m1", state))
    assert record["model_name"] == "MyModel"
    assert record["model_module"] == "my-pkg"
    assert record["model_module_version"] == "^1.2.3"


def test_round_trip_plain_state_is_identity() -> None:
    entry = ("m1", {"value": 42, "_esm": "export default {}"})
    assert load_model(dump_model(entry)) == entry


def test_round_trip_binary_by_raw_bytes() -> None:
    arr = array.array("f", [1.5, 2.5, -3.0])
    entry = ("plot", {"label": "x", "blob": b"\x00\x01", "data": memoryview(arr)})
    model_id, state = load_model(dump_model(entry))
    assert model_id == "plot"
    assert state["label"] == "x"
    assert _raw(state["blob"]) == b"\x00\x01"
    assert _raw(state["data"]) == _raw(memoryview(arr))


def test_dump_model_includes_buffers_when_present() -> None:
    _, record = dump_model(("m1", {"blob": b"abc"}))
    assert record["buffers"] == [{"path": ["blob"], "encoding": "base64", "data": "YWJj"}]
    assert record["state"] == {}  # dict-keyed binary is removed from state


def test_document_envelope_shape() -> None:
    doc = dump_document([("m1", {"value": 1})])
    assert doc["version_major"] == 2
    assert doc["version_minor"] == 0
    assert set(doc["state"]) == {"m1"}
    assert doc["state"]["m1"]["state"] == {"value": 1}


def test_empty_document() -> None:
    doc = dump_document([])
    assert doc == {"version_major": 2, "version_minor": 0, "state": {}}
    assert load_document(doc) == []


def test_round_trip_document_preserves_order() -> None:
    entries = [("a", {"value": 1}), ("b", {"value": 2}), ("c", {"value": 3})]
    assert load_document(dump_document(entries)) == entries
    doc = dump_document(entries)
    assert dump_document(load_document(doc)) == doc


def test_composition_child_refs_preserved_verbatim() -> None:
    # A container references children as "IPY_MODEL_<id>" strings in ordinary state.
    entries: list[ModelEntry] = [
        ("box", {"children": ["IPY_MODEL_slider", "IPY_MODEL_label"]}),
        ("slider", {"value": 10}),
        ("label", {"text": "hi"}),
    ]
    doc = dump_document(entries)
    assert doc["state"]["box"]["state"]["children"] == ["IPY_MODEL_slider", "IPY_MODEL_label"]
    assert {"box", "slider", "label"} == set(doc["state"])
    assert load_document(doc) == entries


def test_reference_cycle_loads_without_recursion() -> None:
    # Mutual references: loading is id-lookup, not inlining, so a cycle is safe.
    entries: list[ModelEntry] = [
        ("a", {"peer": "IPY_MODEL_b"}),
        ("b", {"peer": "IPY_MODEL_a"}),
    ]
    loaded = load_document(dump_document(entries))
    assert loaded == entries
