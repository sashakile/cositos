"""Tests for binary-buffer split/merge (protocol v2 nested rules)."""

from cositos.buffers import put_buffers, remove_buffers


def test_flat_dict_extracts_binary_by_key():
    state = {"n": 1, "blob": b"abc"}
    stripped, paths, buffers = remove_buffers(state)
    assert stripped == {"n": 1}
    assert paths == [["blob"]]
    assert buffers == [b"abc"]


def test_list_slot_becomes_none():
    state = {"xs": [b"a", 2, b"b"]}
    stripped, paths, buffers = remove_buffers(state)
    assert stripped == {"xs": [None, 2, None]}
    assert paths == [["xs", 0], ["xs", 2]]
    assert buffers == [b"a", b"b"]


def test_nested_paths():
    state = {"x": {"ar": b"AA"}, "y": {"shape": [2], "data": b"BB"}}
    stripped, paths, buffers = remove_buffers(state)
    assert stripped == {"x": {}, "y": {"shape": [2]}}
    assert paths == [["x", "ar"], ["y", "data"]]
    assert buffers == [b"AA", b"BB"]


def test_no_binary_returns_original_object():
    state = {"a": 1, "b": [1, 2]}
    stripped, paths, buffers = remove_buffers(state)
    assert stripped is state
    assert paths == []
    assert buffers == []


def test_round_trip_merge_is_inverse_of_split():
    original = {"x": {"ar": b"AA"}, "y": [b"a", 2, {"z": b"c"}]}
    stripped, paths, buffers = remove_buffers(original)
    # stripped is a shallow-cloned structure; rebuild it and merge buffers back.
    put_buffers(stripped, paths, buffers)
    assert stripped == original
