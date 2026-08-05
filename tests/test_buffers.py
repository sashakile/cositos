"""Tests for binary-buffer split/merge (protocol v2 nested rules)."""

import sys
import threading

import pytest

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


def test_remove_buffers_never_mutates_the_process_recursion_limit():
    # Regression (cositos-e53): the old implementation temporarily raised the
    # process-global recursion limit so deep nesting could trip the _MAX_DEPTH cap as a
    # clear ValueError. That global mutation lets concurrent callers observe or restore
    # a stale limit. remove_buffers must never touch it.
    old = sys.getrecursionlimit()
    try:
        stripped, paths, buffers = remove_buffers({"a": b"x"})
        assert sys.getrecursionlimit() == old
        assert stripped == {}
        assert paths == [["a"]] and buffers == [b"x"]
    finally:
        sys.setrecursionlimit(old)


def test_deep_nesting_raises_clear_value_error_with_low_recursion_limit():
    # Deep nesting must yield the deterministic _MAX_DEPTH ValueError, not a raw
    # RecursionError, even when the process recursion limit is far below the nesting
    # depth: the iterative walk consumes no C stack frames, so the depth cap is the only
    # failure mode (cositos-e53).
    state: dict = {}
    node = state
    for _ in range(2000):
        child: dict = {}
        node["n"] = child
        node = child

    old = sys.getrecursionlimit()
    sys.setrecursionlimit(800)  # far below 2000 levels of nesting
    try:
        with pytest.raises(ValueError, match="nesting"):
            remove_buffers(state)
        assert sys.getrecursionlimit() == 800  # untouched by remove_buffers
    finally:
        sys.setrecursionlimit(old)


def test_concurrent_remove_buffers_never_alter_the_recursion_limit():
    # Concurrent extraction must not raise or restore the process-global recursion
    # limit: one caller's call must not disturb another caller's view of the limit
    # (cositos-e53).
    old = sys.getrecursionlimit()
    failures: list[str] = []

    def worker() -> None:
        for _ in range(50):
            if sys.getrecursionlimit() != old:
                failures.append(f"recursion limit changed to {sys.getrecursionlimit()}")
                return
            stripped, paths, buffers = remove_buffers({"x": {"ar": b"AA"}, "y": [b"a", 2]})
            if sys.getrecursionlimit() != old:
                failures.append(f"recursion limit changed to {sys.getrecursionlimit()}")
                return
            if stripped != {"x": {}, "y": [None, 2]} or len(paths) != 2 or len(buffers) != 2:
                failures.append(f"bad extraction result: {stripped} {paths} {buffers}")
                return

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not failures, failures
