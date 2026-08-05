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

#: Max container nesting depth `remove_buffers` will descend before raising a clear error
#: (rather than an opaque ``RecursionError``). Deeper widget state is pathological.
_MAX_DEPTH = 500


class _Frame:
    """An explicit stack frame for the iterative tree walk.

    Each frame represents one container being processed. ``parent_key`` is the key in
    the **parent** container that maps to this frame's state — saved so the child's
    result can be written back into the parent's clone.
    """

    __slots__ = ("state", "ancestors", "depth", "iterator", "clone", "parent_key", "path")

    def __init__(
        self,
        state: Any,
        ancestors: tuple[int, ...],
        depth: int,
        iterator: Any,
        clone: Any,
        parent_key: Any,
        path: list[Any],
    ) -> None:
        self.state = state
        self.ancestors = ancestors
        self.depth = depth
        self.iterator = iterator
        self.clone = clone
        self.parent_key = parent_key
        self.path = path


def _items(substate: Any) -> Iterable[tuple[Any, Any]]:
    """Yield ``(key, value)`` pairs for a list (index keys) or dict (str keys)."""
    if isinstance(substate, (list, tuple)):
        return enumerate(substate)
    return iter(substate.items())  # type: ignore[no-any-return]


def _clone(substate: Any) -> Any:
    return list(substate) if isinstance(substate, (list, tuple)) else dict(substate)


def _extract_binary(clone: Any, key: Any) -> None:
    """Blank a binary slot: ``None`` for list indices, remove for dict keys."""
    if isinstance(clone, list):
        clone[key] = None
    else:
        del clone[key]


def _separate(
    substate: Any,
    path: list[Any],
    buffer_paths: list[list[Any]],
    buffers: list[Any],
    ancestors: tuple[int, ...] = (),
    depth: int = 0,
) -> Any:
    """Iterative walk of dicts/lists, extracting binary values.

    Returns a cloned substate with binary values removed and their locations recorded in
    ``buffer_paths``/``buffers``. Clones a container only when it actually changes,
    mirroring the ipywidgets algorithm so untouched subtrees keep their identity.

    A container that appears among its own ancestors is a cycle, and nesting beyond
    :data:`_MAX_DEPTH` is capped — both raise a clear :class:`ValueError` naming the path
    rather than a ``RecursionError`` (cositos-915). Shared but acyclic subtrees (a DAG)
    are fine: only the current ancestor chain is checked, not every visited node.

    Implemented iteratively (cositos-e53) so the depth cap is the only failure mode: no
    C stack frames are consumed, so no process-global ``sys.setrecursionlimit``
    manipulation is needed in :func:`remove_buffers`.
    """
    if not isinstance(substate, (list, tuple, dict)):
        return substate
    if depth > _MAX_DEPTH:
        raise ValueError(f"state nesting exceeds {_MAX_DEPTH} levels at path {path}")
    if id(substate) in ancestors:
        raise ValueError(f"cyclic reference detected in state at path {path}")
    ancestors = (*ancestors, id(substate))

    # Explicit stack of frames for depth-first traversal.
    stack = [_Frame(substate, ancestors, depth, _items(substate), None, None, path)]

    while stack:
        frame = stack[-1]

        # Advance the current frame's iterator.
        try:
            key, value = next(frame.iterator)
        except StopIteration:
            # Frame complete — pop and return its result.
            stack.pop()
            result = frame.clone if frame.clone is not None else frame.state

            if not stack:
                return result  # Root frame done.

            # Apply the result to the parent frame.
            parent = stack[-1]
            if result is not frame.state:
                if parent.clone is None:
                    parent.clone = _clone(parent.state)
                parent.clone[frame.parent_key] = result
            continue

        if isinstance(value, BinaryType):
            if frame.clone is None:
                frame.clone = _clone(frame.state)
            _extract_binary(frame.clone, key)
            buffers.append(value)
            buffer_paths.append([*frame.path, key])
        elif isinstance(value, (list, tuple, dict)):
            child_depth = frame.depth + 1
            if child_depth > _MAX_DEPTH:
                raise ValueError(f"state nesting exceeds {_MAX_DEPTH} levels at path {frame.path}")
            if id(value) in frame.ancestors:
                raise ValueError(f"cyclic reference detected in state at path {frame.path}")
            child_ancestors = (*frame.ancestors, id(value))
            stack.append(
                _Frame(
                    value,
                    child_ancestors,
                    child_depth,
                    _items(value),
                    None,
                    key,
                    [*frame.path, key],
                )
            )

    return substate  # pragma: no cover


def remove_buffers(state: Any) -> tuple[Any, list[list[Any]], list[Any]]:
    """Return ``(state_without_buffers, buffer_paths, buffers)``.

    Nesting is capped at :data:`_MAX_DEPTH`; the walk is iterative, so no process-global
    recursion-limit mutation is needed (cositos-e53).
    """
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
