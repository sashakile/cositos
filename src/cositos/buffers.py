"""Binary-buffer split/merge, faithful to widget protocol v2 (nested buffer_paths).

A "binary" value is ``bytes``, ``bytearray``, or ``memoryview``. On the wire, binary
values are stripped out of the JSON state into a parallel ``buffers`` list, and their
locations recorded in ``buffer_paths``. A path ending in a dict key is *removed* from
the state; a path ending in a list index is replaced by ``None`` so positions are kept.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import Any

BinaryType = (bytes, bytearray, memoryview)

#: Max container nesting depth `remove_buffers` will descend before raising a clear error
#: (rather than an opaque ``RecursionError``). Deeper widget state is pathological.
_MAX_DEPTH = 500


def _items(substate: Any) -> Iterable[tuple[Any, Any]]:
    """Yield ``(key, value)`` pairs for a list (index keys) or dict (str keys)."""
    if isinstance(substate, (list, tuple)):
        return enumerate(substate)
    return substate.items()  # type: ignore[no-any-return]


def _clone(substate: Any) -> Any:
    return list(substate) if isinstance(substate, (list, tuple)) else dict(substate)


def _extract_binary(clone: Any, key: Any) -> None:
    """Blank a binary slot: ``None`` for list indices, remove for dict keys."""
    if isinstance(clone, list):
        clone[key] = None
    else:
        del clone[key]


def _handle_item(
    substate: Any,
    clone: Any,
    key: Any,
    value: Any,
    path: list[Any],
    buffer_paths: list[list[Any]],
    buffers: list[Any],
    ancestors: tuple[int, ...],
    depth: int,
) -> Any:
    """Process one ``(key, value)``; return the (possibly newly created) clone."""
    if isinstance(value, BinaryType):
        clone = clone if clone is not None else _clone(substate)
        _extract_binary(clone, key)
        buffers.append(value)
        buffer_paths.append([*path, key])
    elif isinstance(value, (list, tuple, dict)):
        new_value = _separate(value, [*path, key], buffer_paths, buffers, ancestors, depth + 1)
        if new_value is not value:
            clone = clone if clone is not None else _clone(substate)
            clone[key] = new_value
    return clone


def _separate(
    substate: Any,
    path: list[Any],
    buffer_paths: list[list[Any]],
    buffers: list[Any],
    ancestors: tuple[int, ...] = (),
    depth: int = 0,
) -> Any:
    """Recurse into dicts/lists, extracting binary values. Returns a cloned substate.

    Clones a container only when it actually changes, mirroring the ipywidgets
    algorithm so untouched subtrees keep their identity. A container that appears among
    its own ancestors is a cycle, and nesting beyond :data:`_MAX_DEPTH` is capped — both
    raise a clear :class:`ValueError` naming the path rather than a ``RecursionError``
    (cositos-915). Shared but acyclic subtrees (a DAG) are fine: only the current
    ancestor chain is checked, not every visited node.
    """
    if not isinstance(substate, (list, tuple, dict)):
        return substate
    if depth > _MAX_DEPTH:
        raise ValueError(f"state nesting exceeds {_MAX_DEPTH} levels at path {path}")
    if id(substate) in ancestors:
        raise ValueError(f"cyclic reference detected in state at path {path}")
    ancestors = (*ancestors, id(substate))

    clone: Any = None
    for key, value in _items(substate):
        clone = _handle_item(
            substate, clone, key, value, path, buffer_paths, buffers, ancestors, depth
        )
    return clone if clone is not None else substate


def remove_buffers(state: Any) -> tuple[Any, list[list[Any]], list[Any]]:
    """Return ``(state_without_buffers, buffer_paths, buffers)``.

    Nesting is capped at :data:`_MAX_DEPTH`; the interpreter recursion limit is
    temporarily raised so that cap (a clear error) trips before a raw ``RecursionError``.
    """
    buffer_paths: list[list[Any]] = []
    buffers: list[Any] = []
    needed = (_MAX_DEPTH + 2) * 2 + 200  # ~2 frames per nesting level, plus headroom
    old_limit = sys.getrecursionlimit()
    try:
        if old_limit < needed:
            sys.setrecursionlimit(needed)
        stripped = _separate(state, [], buffer_paths, buffers)
    finally:
        sys.setrecursionlimit(old_limit)
    return stripped, buffer_paths, buffers


def put_buffers(state: Any, buffer_paths: list[list[Any]], buffers: list[Any]) -> None:
    """Inverse of :func:`remove_buffers`; mutates ``state`` in place.

    ``buffer_paths`` and ``buffers`` must be the same length (``strict=True``); a mismatch
    raises :class:`ValueError` rather than silently leaving a placeholder in ``state`` or
    dropping a buffer (cositos-y07). This matches :func:`encode_buffers_base64`.
    """
    for path, buffer in zip(buffer_paths, buffers, strict=True):
        obj = state
        for key in path[:-1]:
            obj = obj[key]
        obj[path[-1]] = buffer
