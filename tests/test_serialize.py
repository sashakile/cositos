"""Tests for widget-state serialization foundation: types + base64 buffer codec."""

import array

from hypothesis import given
from hypothesis import strategies as st

from cositos.serialize import (
    Document,
    ModelEntry,
    check_references,
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


def test_encode_non_contiguous_memoryview() -> None:
    # Regression (cositos-cnq): a strided/sliced memoryview (common from numpy views) is
    # non-contiguous, so memoryview.cast('B') raises. Encoding must still succeed by
    # copying to contiguous bytes in C order.
    strided = memoryview(bytearray(range(16)))[::2]  # non-contiguous view
    assert not strided.contiguous
    expected = strided.tobytes()  # bytes 0,2,4,...,14
    _, entries = encode_buffers_base64(({}, [["d"]], [strided]))
    _, _, buffers2 = decode_buffers_base64(({}, entries))
    assert buffers2[0] == expected


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


def test_check_references_raises_on_dangling_ref() -> None:
    # Regression (cositos-qzk): a reference to a model absent from the document must be
    # caught, not silently exported into a broken render.
    doc = dump_document([("box", {"_esm": "e", "children": ["IPY_MODEL_ghost"]})])
    try:
        check_references(doc)
    except ValueError as e:
        assert "ghost" in str(e) and "box" in str(e)
    else:
        raise AssertionError("expected ValueError for a dangling IPY_MODEL reference")


def test_check_references_passes_for_resolved_and_shared_refs() -> None:
    # Present refs, a nested ref, and a diamond (two holders -> one child) all resolve.
    doc = dump_document(
        [
            ("box", {"children": ["IPY_MODEL_slider", "IPY_MODEL_label"]}),
            ("panel", {"body": {"main": "IPY_MODEL_slider"}}),
            ("slider", {"value": 1}),
            ("label", {"text": "hi"}),
        ]
    )
    assert check_references(doc) is None  # no raise


def test_check_references_allows_reference_cycle() -> None:
    # Mutual references are integrity-valid (both ids present); only missing ids are errors.
    doc = dump_document([("a", {"peer": "IPY_MODEL_b"}), ("b", {"peer": "IPY_MODEL_a"})])
    assert check_references(doc) is None


def test_load_document_does_not_mutate_input_document() -> None:
    # Regression (cositos-t3c): load must be pure. Mutating record['state'] in place put
    # raw bytes back into the input Document, so a later json.dumps/embed_html raised
    # 'bytes is not JSON serializable'.
    import json

    entries: list[ModelEntry] = [("m1", {"_esm": "x", "blob": b"\x00\x01\x02"})]
    doc = dump_document(entries)
    before = json.dumps(doc)
    loaded = load_document(doc)
    assert json.dumps(doc) == before  # input Document unchanged, still JSON-safe
    assert _raw(dict(loaded)["m1"]["blob"]) == b"\x00\x01\x02"  # load still reconstructs bytes


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


def test_dump_document_rejects_empty_model_id() -> None:
    try:
        dump_document([("", {"value": 1})])
    except ValueError as e:
        assert "model_id" in str(e)
    else:
        raise AssertionError("expected ValueError for empty model_id")


def test_dump_document_rejects_duplicate_model_ids() -> None:
    try:
        dump_document([("dup", {"value": 1}), ("dup", {"value": 2})])
    except ValueError as e:
        assert "dup" in str(e)
    else:
        raise AssertionError("expected ValueError for duplicate model_id")


# --- Property-based round-trip -------------------------------------------------------

_ids = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=6)
_keys = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=6)
_scalars = st.none() | st.booleans() | st.integers() | st.text(max_size=8)
_refs = _ids.map(lambda s: "IPY_MODEL_" + s)  # composition references
_values = _scalars | st.binary(max_size=8) | _refs | st.lists(_scalars, max_size=3)
_states = st.dictionaries(_keys, _values, max_size=4)


@given(st.lists(st.tuples(_ids, _states), unique_by=lambda e: e[0], max_size=5))
def test_document_round_trip_is_identity(entries: list[ModelEntry]) -> None:
    # Binary values are bytes here, so equality holds directly (bytes == bytes). Typed
    # float32 buffers are covered by the golden fixture's raw-byte assertion.
    assert load_document(dump_document(entries)) == entries


def test_document_round_trip_with_float32_and_refs() -> None:
    # A worked example combining a binary buffer, a float32 array, and a child ref.
    arr = array.array("f", [0.5, -1.25])
    entries: list[ModelEntry] = [
        ("root", {"children": ["IPY_MODEL_img"], "blob": b"\x00\xff"}),
        ("img", {"shape": [2], "dtype": "float32", "data": memoryview(arr)}),
    ]
    loaded = dict(load_document(dump_document(entries)))
    assert loaded["root"]["children"] == ["IPY_MODEL_img"]
    assert _raw(loaded["root"]["blob"]) == b"\x00\xff"
    assert _raw(loaded["img"]["data"]) == _raw(memoryview(arr))
