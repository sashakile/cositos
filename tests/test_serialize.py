"""Tests for widget-state serialization foundation: types + base64 buffer codec."""

import array

from cositos.serialize import (
    Document,
    ModelEntry,
    decode_buffers_base64,
    encode_buffers_base64,
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
