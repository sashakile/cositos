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
    return (_build_naive if variant == "A" else _build_mvu)(SCALES[scale])


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

    def one_action() -> tuple[int, bool]:
        guard["needed"] = False
        before = fires["n"]
        brushes[0].value = (0, 1)
        return fires["n"] - before, guard["needed"]

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
    edges: list[tuple[str, str]] = [("event", "update"), ("update", "model")]

    def render() -> None:  # pure projection Model -> views, one pass
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

    def one_action() -> tuple[int, bool]:
        before = fires["n"]
        dispatch(0, (0, 1))  # same user action as variant A
        return fires["n"] - before, False

    return root, edges, one_action
