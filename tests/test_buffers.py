"""Tests for binary-buffer split/merge (protocol v2 nested rules)."""

import sys

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


def test_put_buffers_deeply_nested_path():
    state = {"a": {"b": [{}, {"c": None}]}}
    put_buffers(state, [["a", "b", 1, "c"]], [b"deep"])
    assert state["a"]["b"][1]["c"] == b"deep"


def test_put_buffers_raises_when_fewer_buffers_than_paths():
    # Regression (cositos-y07): a length mismatch must error, not silently leave a
    # placeholder (None) merged into host state on the inbound path.
    state = {"a": None, "b": None}
    try:
        put_buffers(state, [["a"], ["b"]], [b"X"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for fewer buffers than paths")


def test_put_buffers_raises_when_more_buffers_than_paths():
    state = {"a": None}
    try:
        put_buffers(state, [["a"]], [b"X", b"Y"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for more buffers than paths")


def test_remove_buffers_detects_cycle():
    # Regression (cositos-915): a self-referential container must raise a clear error,
    # not recurse forever into a RecursionError.
    state = {"a": 1}
    state["self"] = state
    try:
        remove_buffers(state)
    except ValueError as e:
        assert "cycl" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for a cyclic container")


def test_remove_buffers_caps_deep_nesting():
    # Deep but acyclic nesting must yield a clear error naming the depth, not an opaque
    # RecursionError around the interpreter's stack limit (~500 levels).
    state: dict = {}
    node = state
    for _ in range(2000):
        child: dict = {}
        node["n"] = child
        node = child
    try:
        remove_buffers(state)
    except ValueError as e:
        assert "nesting" in str(e).lower() or "depth" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for excessively deep nesting")


def test_remove_buffers_allows_shared_acyclic_subtrees():
    # A DAG (same dict referenced twice, no cycle) must NOT be misreported as a cycle.
    shared = {"v": 1}
    state = {"a": shared, "b": shared}
    stripped, paths, buffers = remove_buffers(state)
    assert stripped == {"a": {"v": 1}, "b": {"v": 1}}
    assert paths == [] and buffers == []


def test_remove_buffers_raises_recursion_limit_when_below_needed():
    # When the interpreter's recursion limit is below what deep nesting needs,
    # remove_buffers must temporarily raise it (so the _MAX_DEPTH cap trips as a
    # clear ValueError before a raw RecursionError) and restore it afterwards.
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(800)  # below `needed` (~1204), safely above test stack depth
    try:
        stripped, paths, buffers = remove_buffers({"a": b"x"})
    finally:
        sys.setrecursionlimit(old)
    assert stripped == {}
    assert paths == [["a"]] and buffers == [b"x"]
