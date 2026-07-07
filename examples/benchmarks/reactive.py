"""A ~50-line reactive core (tracked signals) for benchmark variant C.

Demonstrates the "tracked acyclic DAG" middle ground between naive peer-to-peer
``observe`` (variant A: incremental but cyclic/unserializable) and whole-model MVU
(variant B: acyclic but coarse — recomputes everything each edit).

* ``Signal`` holds a value; reading it inside a computation records a dependency edge.
* ``Computed`` recomputes only when a dependency it actually read has changed.
* ``Effect`` is a leaf computation (writes to a widget) that re-runs on dependency change.

Propagation follows the recorded dependency graph, so one ``Signal.set`` recomputes exactly
the downstream nodes (incremental, like A) — and because dependencies are *tracked at read
time* the graph is acyclic by construction (like B), with a single source of truth.
"""

from __future__ import annotations

from typing import Any, Callable

_current: list[_Node] = []  # subscriber stack for dependency tracking


class _Node:
    def __init__(self) -> None:
        self.subscribers: set[_Node] = set()

    def _run(self) -> None:  # overridden by Computed/Effect
        ...


class Signal:
    """A mutable reactive value. Reading inside a Computed/Effect records a dependency."""

    def __init__(
        self, value: Any, edges: list[tuple[str, str]] | None = None, name: str = ""
    ) -> None:
        self._value = value
        self._subs: set[_Node] = set()
        self._edges = edges
        self._name = name

    def get(self) -> Any:
        if _current:
            sub = _current[-1]
            self._subs.add(sub)
            if self._edges is not None:
                self._edges.append((self._name, getattr(sub, "name", "?")))
        return self._value

    def set(self, value: Any) -> None:
        if value == self._value:
            return
        self._value = value
        for sub in list(self._subs):  # notify only actual dependents
            sub._run()


class Computed(_Node):
    def __init__(
        self,
        fn: Callable[[], Any],
        name: str,
        counter: dict[str, int],
        edges: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self._fn = fn
        self.name = name
        self._counter = counter
        self._edges = edges
        self._value: Any = None
        self._subs: set[_Node] = set()
        self._run()

    def _run(self) -> None:
        # Computed recomputes are NOT counted in the storm metric — only Effects (output
        # refreshes) are, so storm means the same unit across A/B/C (see benchlib).
        _current.append(self)
        try:
            new = self._fn()
        finally:
            _current.pop()
        if new != self._value:
            self._value = new
            for sub in list(self._subs):
                sub._run()

    def get(self) -> Any:
        if _current:
            self._subs.add(_current[-1])
            if self._edges is not None:
                self._edges.append((self.name, getattr(_current[-1], "name", "?")))
        return self._value


class Effect(_Node):
    def __init__(self, fn: Callable[[], None], name: str, counter: dict[str, int]) -> None:
        super().__init__()
        self._fn = fn
        self.name = name
        self._counter = counter
        self._run()

    def _run(self) -> None:
        self._counter["n"] += 1
        _current.append(self)
        try:
            self._fn()
        finally:
            _current.pop()
