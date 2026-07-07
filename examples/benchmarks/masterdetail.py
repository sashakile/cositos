"""Scenario: master-detail — stresses fan-out and linked "master" controls.

One selection (the master) drives many dependent detail views. Two twists that tangle the
naive version: several master controls (a dropdown + a list + a breadcrumb) are kept in
sync with each other, and every detail depends on the selection.

* variant A (naive): the master controls are ``link``ed pairwise into a clique (O(k^2)
  bidirectional links -> cycles), and every detail ``observe``s the master -> O(details)
  fan-out edges. One selection change propagates around the clique and re-fires all details.
* variant B (MVU): selection lives in one Model; each master control dispatches a
  ``set_selection`` message; details are pure projections rendered once. Acyclic; the
  master controls are consistent because they all read the same model, not each other.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import ipywidgets as W
from reactive import Computed, Effect, Signal


@dataclass(frozen=True)
class Config:
    items: int  # selectable master items
    details: int  # dependent detail views (fan-out)
    masters: int  # linked master controls (clique)
    depth: int
    shared: int
    seed: int = 0

    @property
    def label(self) -> str:
        return (
            f"items={self.items} details={self.details} masters={self.masters} "
            f"depth={self.depth} shared={self.shared}"
        )


SCALES: dict[str, Config] = {
    "small": Config(items=10, details=6, masters=3, depth=3, shared=2),
    "complex": Config(items=50, details=30, masters=4, depth=6, shared=6),
    "big": Config(items=200, details=150, masters=6, depth=8, shared=20),
}

VARIANTS = ("A", "B", "C")  # also has a reactive-DAG variant


def _facts(cfg: Config) -> list[int]:
    rng = random.Random(cfg.seed)
    return [rng.randrange(1000) for _ in range(cfg.items)]


def _nest(items: list[Any], depth: int) -> Any:
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
    builder = {"A": _build_naive, "B": _build_mvu, "C": _build_reactive}[variant]
    return builder(SCALES[scale])


def _build_naive(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    facts = _facts(cfg)
    opts = list(range(cfg.items))
    masters = [W.Dropdown(options=opts, value=0) for _ in range(cfg.masters)]
    shared_legends = [W.HTML(value=f"legend {i}") for i in range(cfg.shared)]

    edges: list[tuple[str, str]] = []
    fires = {"n": 0}
    links = []

    # master clique: link every pair of master controls (bidirectional -> cycles)
    for i in range(cfg.masters):
        for j in range(i + 1, cfg.masters):
            links.append(W.link((masters[i], "value"), (masters[j], "value")))
            edges += [(f"master{i}", f"master{j}"), (f"master{j}", f"master{i}")]

    details: list[Any] = []
    for k in range(cfg.details):
        out = W.Label()

        def recompute(_c: Any = None, k: int = k, out: Any = out) -> None:
            fires["n"] += 1
            sel = masters[0].value
            out.value = f"detail{k}: item {sel} = {facts[sel]}"

        masters[0].observe(recompute, names="value")  # every detail observes the master
        edges.append(("master0", f"detail{k}"))
        details.append(W.VBox([out, shared_legends[k % cfg.shared]]))

    root = W.VBox([W.HBox(masters), _nest(details, cfg.depth)])
    root._benchmark_links = links

    def one_action() -> tuple[int, bool, int]:
        before = fires["n"]
        masters[1].value = 3  # change one master -> clique propagation + detail fan-out
        return fires["n"] - before, False, 0

    return root, edges, one_action


def _build_mvu(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    facts = _facts(cfg)
    opts = list(range(cfg.items))
    state = {"selection": 0}
    masters = [W.Dropdown(options=opts, value=0) for _ in range(cfg.masters)]
    shared_legends = [W.HTML(value=f"legend {i}") for i in range(cfg.shared)]
    detail_labels = [W.Label() for _ in range(cfg.details)]
    details = [
        W.VBox([detail_labels[k], shared_legends[k % cfg.shared]]) for k in range(cfg.details)
    ]
    root = W.VBox([W.HBox(masters), _nest(details, cfg.depth)])

    fires = {"n": 0}
    syncing = {"flag": False}
    edges: list[tuple[str, str]] = [("event", "update"), ("update", "model")]

    def render() -> None:
        sel = state["selection"]
        for k, lbl in enumerate(detail_labels):
            fires["n"] += 1
            lbl.value = f"detail{k}: item {sel} = {facts[sel]}"
        syncing["flag"] = True  # programmatic master sync must not echo back as events
        try:
            for m in masters:  # masters are also projections of the model (kept consistent)
                if m.value != sel:
                    m.value = sel
        finally:
            syncing["flag"] = False

    def dispatch(sel: int) -> None:
        if syncing["flag"]:
            return
        state["selection"] = sel
        render()

    for i, m in enumerate(masters):
        m.observe(lambda ch: dispatch(ch["new"]), names="value")
        edges.append((f"master{i}", "event"))
    for k in range(cfg.details):
        edges.append(("model", f"detail{k}"))

    render()

    def one_action() -> tuple[int, bool, int]:
        before = fires["n"]
        masters[1].value = 3
        return fires["n"] - before, False, 0

    return root, edges, one_action


def _build_reactive(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    """Variant C: one selection signal; details are computeds; masters sync via an effect.

    The naive clique of linked masters collapses to a single source (all masters read and
    write one selection signal), so the graph is acyclic. Every detail depends on the
    selection, so a change recomputes all details (inherent fan-out) — but with no cycle.
    """
    facts = _facts(cfg)
    opts = list(range(cfg.items))
    edges: list[tuple[str, str]] = []
    counter = {"n": 0}

    selection = Signal(0, edges, name="selection")
    masters = [W.Dropdown(options=opts, value=0) for _ in range(cfg.masters)]
    for m in masters:  # any master edits the single source; equal-value sets are ignored
        m.observe(lambda ch: selection.set(ch["new"]), names="value")

    shared_legends = [W.HTML(value=f"legend {i}") for i in range(cfg.shared)]
    details: list[Any] = []
    for k in range(cfg.details):
        label = W.Label()

        def compute(k: int = k) -> str:
            sel = selection.get()
            return f"detail{k}: item {sel} = {facts[sel]}"

        c = Computed(compute, name=f"detail{k}", counter=counter, edges=edges)
        Effect(
            lambda label=label, c=c: setattr(label, "value", c.get()),
            name=f"detaile{k}", counter=counter,
        )
        details.append(W.VBox([label, shared_legends[k % cfg.shared]]))

    # one effect keeps every master control consistent with the selection
    def sync_masters() -> None:
        sel = selection.get()
        for m in masters:
            if m.value != sel:
                m.value = sel

    Effect(sync_masters, name="mastersync", counter=counter)

    root = W.VBox([W.HBox(masters), _nest(details, cfg.depth)])

    def one_action() -> tuple[int, bool, int]:
        before = counter["n"]
        masters[1].value = 3
        return counter["n"] - before, False, 0

    return root, edges, one_action
