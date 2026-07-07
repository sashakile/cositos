"""A small glitch-free reactive core (tracked signals) for benchmark variants C/D.

Demonstrates the "tracked acyclic DAG" middle ground between naive peer-to-peer ``observe``
(incremental but cyclic/unserializable) and whole-model MVU (acyclic but coarse).

* ``Signal`` holds a value; reading it inside a computation records a dependency.
* ``Computed`` is a lazily-recomputed, memoized derivation of its dependencies.
* ``Effect`` is a leaf computation (writes a widget) that re-runs when a dependency changes.

Propagation is **mark-and-pull**: a ``Signal.set`` marks transitive dependents dirty and
queues affected effects; each effect then *pulls* the computeds it reads, which recompute
at most once (memoized, reading already-refreshed inputs). This is glitch-free — a node
reachable by two paths (a diamond) recomputes exactly once with consistent inputs — unlike
naive push, which double-fires. A recompute cycle raises rather than looping forever.

Only ``Effect`` runs are counted in the storm metric (one unit per output refresh), so the
metric means the same thing across the naive/MVU/reactive variants (see benchlib).
"""

from __future__ import annotations

from typing import Any, Callable

_current: list[Computed | Effect] = []  # subscriber stack for dependency tracking
_pending: list[Effect] = []  # effects queued for the current flush
_recompute_stack: list[Computed] = []  # cycle guard


def _subscribe(source: Signal | Computed) -> None:
    """Record that the currently-running node depends on ``source``."""
    if not _current:
        return
    sub = _current[-1]
    source._subs.add(sub)
    sub._sources.add(source)
    if source._edges is not None:
        source._edges.append((source.name, sub.name))


def _flush() -> None:
    while _pending:
        _pending.pop(0)._run()


class Signal:
    """A mutable reactive value. Reading inside a Computed/Effect records a dependency."""

    def __init__(
        self, value: Any, edges: list[tuple[str, str]] | None = None, name: str = ""
    ) -> None:
        self._value = value
        self._subs: set[Computed | Effect] = set()
        self._edges = edges
        self.name = name

    def get(self) -> Any:
        _subscribe(self)
        return self._value

    def set(self, value: Any) -> None:
        if value == self._value:
            return
        self._value = value
        for node in list(self._subs):
            node._invalidate()
        _flush()


class Computed:
    """A memoized derivation; recomputes lazily (on read) after a dependency changes."""

    def __init__(
        self,
        fn: Callable[[], Any],
        name: str,
        counter: dict[str, int],
        edges: list[tuple[str, str]] | None = None,
    ) -> None:
        self._fn = fn
        self.name = name
        self._counter = counter  # kept for API symmetry; only Effects count toward storm
        self._edges = edges
        self._value: Any = None
        self._dirty = True
        self._subs: set[Computed | Effect] = set()
        self._sources: set[Signal | Computed] = set()

    def _invalidate(self) -> None:
        if not self._dirty:
            self._dirty = True
            for node in list(self._subs):  # propagate staleness to dependents
                node._invalidate()

    def mark_stale(self) -> None:
        """Force re-evaluation (e.g. after the dependency *set* itself changed shape)."""
        self._dirty = True
        for node in list(self._subs):
            node._invalidate()
        _flush()

    def _recompute(self) -> None:
        for s in self._sources:  # clear old subscriptions, rebuilt on this run
            s._subs.discard(self)
        self._sources.clear()
        self._dirty = False
        _recompute_stack.append(self)
        _current.append(self)
        try:
            self._value = self._fn()
        finally:
            _current.pop()
            _recompute_stack.pop()

    def get(self) -> Any:
        if self in _recompute_stack:  # re-entrant read during our own computation = cycle
            raise RuntimeError(f"reactive cycle through computed {self.name!r}")
        if self._dirty:
            self._recompute()
        _subscribe(self)
        return self._value


class Effect:
    """A leaf computation (writes to a widget) that re-runs when a dependency changes."""

    def __init__(self, fn: Callable[[], None], name: str, counter: dict[str, int]) -> None:
        self._fn = fn
        self.name = name
        self._counter = counter
        self._sources: set[Signal | Computed] = set()
        self._run()

    def _invalidate(self) -> None:
        if self not in _pending:
            _pending.append(self)

    def _run(self) -> None:
        self._counter["n"] += 1  # storm = output refreshes: counted here only
        for s in self._sources:
            s._subs.discard(self)
        self._sources.clear()
        _current.append(self)
        try:
            self._fn()
        finally:
            _current.pop()
