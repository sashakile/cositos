"""Scenario: dynamic structure — add/remove rows at runtime (reconciliation cost).

Unlike the other scenarios (fixed widget tree, only values change), here the *number* of
widgets changes: one action adds `churn` rows to a live list. This is where the earlier
verdict flips.

* variant A (naive incremental): create only the new row widgets and append them.
* variant B (MVU rebuild): re-render the children list from the model, which **rebuilds
  every row widget** (no keys/vdom) — the reconciliation cost.
* variant C (reactive): create only the new rows' signals/effects and append.

Headline metric: `created` — widgets constructed for one action. Incremental styles create
`churn` rows; naive MVU recreates all `rows + churn`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ipywidgets as W
from reactive import Computed, Effect, Signal

_PER_ROW = 3  # widgets built per row: FloatText + Label + VBox (legend is shared)


@dataclass(frozen=True)
class Config:
    rows: int
    churn: int  # rows added in one action
    depth: int
    shared: int

    @property
    def label(self) -> str:
        return f"rows={self.rows} churn={self.churn} depth={self.depth} shared={self.shared}"


SCALES: dict[str, Config] = {
    "small": Config(rows=5, churn=3, depth=3, shared=2),
    "complex": Config(rows=30, churn=10, depth=6, shared=6),
    "big": Config(rows=100, churn=20, depth=8, shared=20),
}

VARIANTS = ("A", "B", "C")


def build(variant: str, scale: str) -> tuple[Any, list[tuple[str, str]], Any]:
    return {"A": _build_naive, "B": _build_mvu, "C": _build_reactive}[variant](SCALES[scale])


def _build_naive(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    edges: list[tuple[str, str]] = []
    fires = {"n": 0}
    created = {"n": 0}
    legends = [W.HTML(value=f"help {i}") for i in range(cfg.shared)]
    inputs: list[W.FloatText] = []
    container = W.VBox([])
    grand = W.Label()

    def recompute(_c: Any = None) -> None:
        fires["n"] += 1
        grand.value = f"total={sum(w.value for w in inputs)}"

    def add_row(i: int) -> Any:
        created["n"] += _PER_ROW
        inp = W.FloatText(value=1.0)
        inp.observe(recompute, names="value")  # each row wires into the grand total
        edges.append((f"row{i}", "total"))
        inputs.append(inp)
        return W.VBox([inp, W.Label(value=f"row {i}"), legends[i % cfg.shared]])

    rows_widgets = [add_row(i) for i in range(cfg.rows)]
    container.children = tuple(rows_widgets)
    recompute()
    root = W.VBox([grand, container])

    def one_action() -> tuple[int, bool, int, int]:
        fbefore, cbefore = fires["n"], created["n"]
        base = len(container.children)
        new = [add_row(base + j) for j in range(cfg.churn)]
        container.children = (*container.children, *new)  # append only the new rows
        recompute()
        return fires["n"] - fbefore, False, 0, created["n"] - cbefore

    return root, edges, one_action


def _build_mvu(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    edges: list[tuple[str, str]] = [("event", "update"), ("update", "model")]
    fires = {"n": 0}
    created = {"n": 0}
    legends = [W.HTML(value=f"help {i}") for i in range(cfg.shared)]
    model: list[float] = [1.0] * cfg.rows
    container = W.VBox([])
    grand = W.Label()

    def render() -> None:
        # rebuild the whole children list from the model (no keys) -> recreates every row
        kids = []
        for i, v in enumerate(model):
            created["n"] += _PER_ROW
            fires["n"] += 1
            kids.append(
                W.VBox([W.FloatText(value=v), W.Label(value=f"row {i}"), legends[i % cfg.shared]])
            )
        container.children = tuple(kids)
        grand.value = f"total={sum(model)}"

    render()
    root = W.VBox([grand, container])
    for i in range(cfg.rows):
        edges.append(("model", f"row{i}"))

    def one_action() -> tuple[int, bool, int, int]:
        fbefore, cbefore = fires["n"], created["n"]
        model.extend([1.0] * cfg.churn)
        render()  # full rebuild
        return fires["n"] - fbefore, False, 0, created["n"] - cbefore

    return root, edges, one_action


def _build_reactive(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    edges: list[tuple[str, str]] = []
    counter = {"n": 0}
    created = {"n": 0}
    legends = [W.HTML(value=f"help {i}") for i in range(cfg.shared)]
    item_sigs: list[Signal] = []
    container = W.VBox([])
    grand = W.Label()

    total_c = Computed(
        lambda: sum(s.get() for s in item_sigs), name="total", counter=counter, edges=edges
    )
    Effect(
        lambda: setattr(grand, "value", f"total={total_c.get()}"), name="totale", counter=counter
    )

    def add_row(i: int) -> Any:
        created["n"] += _PER_ROW
        sig = Signal(1.0, edges, name=f"row{i}")
        item_sigs.append(sig)
        inp = W.FloatText(value=1.0)
        inp.observe(lambda ch, sig=sig: sig.set(ch["new"]), names="value")
        return W.VBox([inp, W.Label(value=f"row {i}"), legends[i % cfg.shared]])

    container.children = tuple(add_row(i) for i in range(cfg.rows))
    root = W.VBox([grand, container])

    def one_action() -> tuple[int, bool, int, int]:
        cbefore, rbefore = created["n"], counter["n"]
        base = len(container.children)
        new = [add_row(base + j) for j in range(cfg.churn)]
        container.children = (*container.children, *new)  # append only new rows
        total_c.mark_stale()  # dependency set changed (new signals); recompute once
        return counter["n"] - rbefore, False, 0, created["n"] - cbefore

    return root, edges, one_action
