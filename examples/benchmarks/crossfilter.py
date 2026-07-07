"""Scenario: cross-filter dashboard — stresses cyclic peer links and update storms.

A synthetic categorical dataset with a filter panel and many summary views that all
reflect the current filter. "Cross-filter" = brushing one view narrows the others.

* variant A (naive): every view ``observe``s every filter; brushes are ``link``ed through
  a shared hub; cross-filtering writes back into filters -> dense, cyclic graph.
* variant B (MVU): one Model; a user action is one ``update``; views are pure projections
  re-rendered in a single pass -> acyclic, single source of truth.

Deliberately includes deep nesting, many elements, and shared/repeated widgets.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import ipywidgets as W
from reactive import Computed, Effect, Signal


@dataclass(frozen=True)
class Config:
    dims: int
    cats: int
    views: int
    depth: int
    shared: int
    rows: int
    seed: int = 0

    @property
    def label(self) -> str:
        return (
            f"dims={self.dims} cats={self.cats} views={self.views} "
            f"depth={self.depth} shared={self.shared}"
        )


SCALES: dict[str, Config] = {
    "small": Config(dims=4, cats=4, views=6, depth=3, shared=2, rows=500),
    "complex": Config(dims=8, cats=6, views=24, depth=6, shared=6, rows=2000),
    "big": Config(dims=16, cats=8, views=100, depth=8, shared=20, rows=8000),
}

VARIANTS = ("A", "B", "C", "D")  # A naive, B MVU, C reactive, D reactive+shared memo


def _dataset(cfg: Config) -> list[tuple[int, ...]]:
    rng = random.Random(cfg.seed)
    return [tuple(rng.randrange(cfg.cats) for _ in range(cfg.dims)) for _ in range(cfg.rows)]


def _count(data: list[tuple[int, ...]], filters: dict[int, set[int]]) -> int:
    return sum(
        1 for row in data if all(not sel or row[d] in sel for d, sel in filters.items())
    )


def _nest(items: list[Any], depth: int) -> Any:
    """Wrap items in a deep, heterogeneous container tree (VBox/HBox/Tab/Accordion)."""
    if depth <= 1 or len(items) <= 2:
        return W.VBox(items)
    mid = len(items) // 2
    left, right = _nest(items[:mid], depth - 1), _nest(items[mid:], depth - 1)
    kind = depth % 4
    if kind == 0:
        return W.Accordion(children=[left, right])
    if kind == 1:
        return W.HBox([left, right])
    if kind == 2:
        return W.Tab(children=[left, right])
    return W.VBox([left, right])


def build(variant: str, scale: str) -> tuple[Any, list[tuple[str, str]], Any]:
    builder = {
        "A": _build_naive, "B": _build_mvu, "C": _build_reactive, "D": _build_shared_reactive
    }[variant]
    return builder(SCALES[scale])


def _build_naive(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    data = _dataset(cfg)
    filters = [
        W.SelectMultiple(options=list(range(cfg.cats)), description=f"d{d}")
        for d in range(cfg.dims)
    ]
    shared_legends = [W.HTML(value=f"legend {i}") for i in range(cfg.shared)]
    hub = W.SelectMultiple(options=list(range(cfg.cats)))

    edges: list[tuple[str, str]] = []
    fires = {"n": 0}
    scans = {"n": 0}
    guard = {"needed": False}
    busy = {"flag": False}
    links = []
    brushes: list[W.SelectMultiple] = []
    views: list[Any] = []

    for v in range(cfg.views):
        summary = W.Label()
        brush = W.SelectMultiple(options=list(range(cfg.cats)))
        brushes.append(brush)

        def recompute(_c: Any = None, v: int = v, summary: Any = summary) -> None:
            fires["n"] += 1
            scans["n"] += 1
            active = {d: set(f.value) for d, f in enumerate(filters) if f.value}
            summary.value = f"view{v}: {_count(data, active)} rows"

        for d, f in enumerate(filters):  # every view observes every filter
            f.observe(recompute, names="value")
            edges.append((f"filter{d}", f"view{v}"))
        hub.observe(recompute, names="value")
        edges.append(("hub", f"view{v}"))

        def writeback(change: Any, v: int = v) -> None:  # cross-filter write-back -> cycle
            if busy["flag"]:
                guard["needed"] = True
                return
            busy["flag"] = True
            try:
                filters[v % cfg.dims].value = tuple(change["new"])
            finally:
                busy["flag"] = False

        brush.observe(writeback, names="value")
        edges.append((f"view{v}", f"filter{v % cfg.dims}"))
        links.append(W.link((brush, "value"), (hub, "value")))
        edges += [(f"view{v}", "hub"), ("hub", f"view{v}")]

        views.append(W.VBox([summary, brush, shared_legends[v % cfg.shared]]))

    root = W.VBox([W.VBox(filters), _nest(views, cfg.depth)])
    root._benchmark_links = links  # keep links alive (unreferenced ipywidgets links die)

    def one_action() -> tuple[int, bool, int]:
        guard["needed"] = False
        before, sbefore = fires["n"], scans["n"]
        brushes[0].value = (0, 1)
        return fires["n"] - before, guard["needed"], scans["n"] - sbefore

    return root, edges, one_action


def _build_mvu(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    data = _dataset(cfg)
    filters_state: dict[int, set[int]] = {}
    shared_legends = [W.HTML(value=f"legend {i}") for i in range(cfg.shared)]
    summaries = [W.Label() for _ in range(cfg.views)]
    view_panels = [W.VBox([summaries[v], shared_legends[v % cfg.shared]]) for v in range(cfg.views)]
    filter_widgets = [
        W.SelectMultiple(options=list(range(cfg.cats)), description=f"d{d}")
        for d in range(cfg.dims)
    ]
    root = W.VBox([W.VBox(filter_widgets), _nest(view_panels, cfg.depth)])

    fires = {"n": 0}
    scans = {"n": 0}
    edges: list[tuple[str, str]] = [("event", "update"), ("update", "model")]

    def render() -> None:  # pure projection Model -> views, one pass
        scans["n"] += 1
        active = {d: sel for d, sel in filters_state.items() if sel}
        count = _count(data, active)
        for v, summary in enumerate(summaries):
            fires["n"] += 1
            summary.value = f"view{v}: {count} rows"

    def dispatch(dim: int, sel: tuple[int, ...]) -> None:
        filters_state[dim] = set(sel)
        render()

    for d, fw in enumerate(filter_widgets):
        fw.observe(lambda ch, d=d: dispatch(d, ch["new"]), names="value")
        edges.append((f"filter{d}", "event"))
    for v in range(cfg.views):
        edges.append(("model", f"view{v}"))

    render()

    def one_action() -> tuple[int, bool, int]:
        before, sbefore = fires["n"], scans["n"]
        dispatch(0, (0, 1))  # same user action as variant A
        return fires["n"] - before, False, scans["n"] - sbefore

    return root, edges, one_action


def _build_reactive(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    """Variant C: filters are signals; each view is a computed over them.

    Every view genuinely depends on every filter, so the tracked graph is dense and one
    filter change recomputes all views (like B) — but it stays acyclic and single-source,
    unlike A. An honest result: reactivity is not incremental when the dependency is real.
    """
    data = _dataset(cfg)
    edges: list[tuple[str, str]] = []
    counter = {"n": 0}
    scans = {"n": 0}

    filter_sigs = [Signal(frozenset(), edges, name=f"filter{d}") for d in range(cfg.dims)]
    filter_widgets = [
        W.SelectMultiple(options=list(range(cfg.cats)), description=f"d{d}")
        for d in range(cfg.dims)
    ]
    for d, w in enumerate(filter_widgets):
        w.observe(lambda ch, d=d: filter_sigs[d].set(frozenset(ch["new"])), names="value")

    shared_legends = [W.HTML(value=f"legend {i}") for i in range(cfg.shared)]
    views: list[Any] = []
    brushes: list[W.SelectMultiple] = []
    for v in range(cfg.views):
        summary = W.Label()
        brush = W.SelectMultiple(options=list(range(cfg.cats)))
        brushes.append(brush)

        def compute(v: int = v) -> str:
            scans["n"] += 1
            active = {d: set(s.get()) for d, s in enumerate(filter_sigs) if s.get()}
            return f"view{v}: {_count(data, active)} rows"

        c = Computed(compute, name=f"view{v}", counter=counter, edges=edges)
        Effect(
            lambda summary=summary, c=c: setattr(summary, "value", c.get()),
            name=f"viewe{v}", counter=counter,
        )
        # cross-filter: brushing a view is just setting a filter signal (single source)
        brush.observe(
            lambda ch, v=v: filter_sigs[v % cfg.dims].set(frozenset(ch["new"])), names="value"
        )
        views.append(W.VBox([summary, brush, shared_legends[v % cfg.shared]]))

    root = W.VBox([W.VBox(filter_widgets), _nest(views, cfg.depth)])

    def one_action() -> tuple[int, bool, int]:
        before, sbefore = counter["n"], scans["n"]
        filter_sigs[0].set(frozenset({0, 1}))
        return counter["n"] - before, False, scans["n"] - sbefore

    return root, edges, one_action


def _build_shared_reactive(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    """Variant D: reactive with a SHARED memoized intermediate.

    Editing EDGE-002: variant C recomputes the O(rows) scan once per view (V redundant
    scans, hidden by the refresh-count metric). Here a single shared Computed does the scan
    once; each view reads that memoized result. This makes the reactive cost tie MVU (both
    scan once) instead of secretly losing V-to-1 — the honest comparison.
    """
    data = _dataset(cfg)
    edges: list[tuple[str, str]] = []
    counter = {"n": 0}
    scans = {"n": 0}

    filter_sigs = [Signal(frozenset(), edges, name=f"filter{d}") for d in range(cfg.dims)]
    filter_widgets = [
        W.SelectMultiple(options=list(range(cfg.cats)), description=f"d{d}")
        for d in range(cfg.dims)
    ]
    for d, w in enumerate(filter_widgets):
        w.observe(lambda ch, d=d: filter_sigs[d].set(frozenset(ch["new"])), names="value")

    def scan() -> int:  # the single shared expensive computation
        scans["n"] += 1
        active = {d: set(s.get()) for d, s in enumerate(filter_sigs) if s.get()}
        return _count(data, active)

    count_c = Computed(scan, name="count", counter=counter, edges=edges)

    shared_legends = [W.HTML(value=f"legend {i}") for i in range(cfg.shared)]
    views: list[Any] = []
    for v in range(cfg.views):
        summary = W.Label()
        brush = W.SelectMultiple(options=list(range(cfg.cats)))
        Effect(
            lambda summary=summary, v=v: setattr(
                summary, "value", f"view{v}: {count_c.get()} rows"
            ),
            name=f"viewe{v}", counter=counter,
        )
        brush.observe(
            lambda ch, v=v: filter_sigs[v % cfg.dims].set(frozenset(ch["new"])), names="value"
        )
        views.append(W.VBox([summary, brush, shared_legends[v % cfg.shared]]))

    root = W.VBox([W.VBox(filter_widgets), _nest(views, cfg.depth)])

    def one_action() -> tuple[int, bool, int]:
        before, sbefore = counter["n"], scans["n"]
        filter_sigs[0].set(frozenset({0, 1}))
        return counter["n"] - before, False, scans["n"] - sbefore

    return root, edges, one_action
