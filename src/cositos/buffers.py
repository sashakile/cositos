"""Binary-buffer split/merge, faithful to widget protocol v2 (nested buffer_paths).

A "binary" value is ``bytes``, ``bytearray``, or ``memoryview``. On the wire, binary
values are stripped out of the JSON state into a parallel ``buffers`` list, and their
locations recorded in ``buffer_paths``. A path ending in a dict key is *removed* from
the state; a path ending in a list index is replaced by ``None`` so positions are kept.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

BinaryType = (bytes, bytearray, memoryview)


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
) -> Any:
    """Process one ``(key, value)``; return the (possibly newly created) clone."""
    if isinstance(value, BinaryType):
        clone = clone if clone is not None else _clone(substate)
        _extract_binary(clone, key)
        buffers.append(value)
        buffer_paths.append([*path, key])
    elif isinstance(value, (list, tuple, dict)):
        new_value = _separate(value, [*path, key], buffer_paths, buffers)
        if new_value is not value:
            clone = clone if clone is not None else _clone(substate)
            clone[key] = new_value
    return clone


def _separate(
    substate: Any, path: list[Any], buffer_paths: list[list[Any]], buffers: list[Any]
) -> Any:
    """Recurse into dicts/lists, extracting binary values. Returns a cloned substate.

    Clones a container only when it actually changes, mirroring the ipywidgets
    algorithm so untouched subtrees keep their identity.
    """
    if not isinstance(substate, (list, tuple, dict)):
        return substate

    clone: Any = None
    for key, value in _items(substate):
        clone = _handle_item(substate, clone, key, value, path, buffer_paths, buffers)
    return clone if clone is not None else substate


def remove_buffers(state: Any) -> tuple[Any, list[list[Any]], list[Any]]:
    """Return ``(state_without_buffers, buffer_paths, buffers)``."""
    buffer_paths: list[list[Any]] = []
    buffers: list[Any] = []
    stripped = _separate(state, [], buffer_paths, buffers)
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
