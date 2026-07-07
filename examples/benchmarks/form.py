"""Scenario: validated form — stresses derived-state chains and cross-field validation.

A form with many inputs, a chain of derived (computed) fields, a grand-total that depends
on every input, mutual cross-field validation, and a submit button enabled only when
valid. This is where naive ``observe`` wiring tangles: derived values cascade down the
chain, validation pairs observe each other (cycles), and one edit re-fires a web of
callbacks.

* variant A (naive): each derived field ``observe``s the previous one; validation pairs
  observe each other; the grand-total observes every input; submit observes every error.
* variant B (MVU): one Model holds all field values; ``validate`` and ``derive`` are pure
  functions of the model; one edit dispatches once and re-renders every dependent widget
  in a single acyclic pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ipywidgets as W
from reactive import Computed, Effect, Signal


@dataclass(frozen=True)
class Config:
    sections: int
    fields_per_section: int
    chain: int  # length of the derived-field dependency chain
    depth: int
    shared: int

    @property
    def n_fields(self) -> int:
        return self.sections * self.fields_per_section

    @property
    def label(self) -> str:
        return (
            f"fields={self.n_fields} chain={self.chain} "
            f"depth={self.depth} shared={self.shared}"
        )


SCALES: dict[str, Config] = {
    "small": Config(sections=2, fields_per_section=3, chain=3, depth=3, shared=2),
    "complex": Config(sections=6, fields_per_section=5, chain=8, depth=6, shared=6),
    "big": Config(sections=16, fields_per_section=8, chain=20, depth=8, shared=20),
}

VARIANTS = ("A", "B", "C")  # this scenario also has a reactive-DAG variant


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
    n = cfg.n_fields
    inputs = [W.FloatText(value=0.0, description=f"f{i}") for i in range(n)]
    errors = [W.Label() for _ in range(n)]
    derived = [W.Label() for _ in range(cfg.chain)]
    grand_total = W.Label()
    submit = W.Button(description="submit")
    shared_legends = [W.HTML(value=f"help {i}") for i in range(cfg.shared)]

    edges: list[tuple[str, str]] = []
    fires = {"n": 0}

    # cross-field validation pairs: field 2k must be <= field 2k+1 (mutual -> cycle)
    def make_validator(a: int, b: int):
        def validate(_c: Any = None) -> None:
            fires["n"] += 1
            ok = inputs[a].value <= inputs[b].value
            errors[a].value = "" if ok else f"f{a} must be <= f{b}"

        return validate

    for k in range(n // 2):
        a, b = 2 * k, 2 * k + 1
        val = make_validator(a, b)
        inputs[a].observe(val, names="value")
        inputs[b].observe(val, names="value")
        edges += [(f"in{a}", f"in{b}"), (f"in{b}", f"in{a}")]

    # derived chain: d0 <- input0; d_i <- d_{i-1} + input_i (cascades on edit)
    def make_derive(i: int):
        def derive(_c: Any = None) -> None:
            fires["n"] += 1
            prev = derived[i - 1].value if i > 0 else "0"
            derived[i].value = f"d{i}({prev},{inputs[i % n].value})"

        return derive

    for i in range(cfg.chain):
        d = make_derive(i)
        if i == 0:
            inputs[0].observe(d, names="value")
            edges.append(("in0", "d0"))
        else:
            derived[i - 1].observe(d, names="value")
            edges.append((f"d{i - 1}", f"d{i}"))
        inputs[i % n].observe(d, names="value")
        edges.append((f"in{i % n}", f"d{i}"))

    # grand total observes every input (fan-in)
    def total(_c: Any = None) -> None:
        fires["n"] += 1
        grand_total.value = f"total={sum(w.value for w in inputs)}"

    for i, w in enumerate(inputs):
        w.observe(total, names="value")
        edges.append((f"in{i}", "total"))

    # submit enabled only if no errors: observes every error label
    def refresh_submit(_c: Any = None) -> None:
        fires["n"] += 1
        submit.disabled = any(e.value for e in errors)

    for k in range(n):
        errors[k].observe(refresh_submit, names="value")
        edges.append((f"err{k}", "submit"))

    rows = [W.VBox([inputs[i], errors[i], shared_legends[i % cfg.shared]]) for i in range(n)]
    root = W.VBox([_nest(rows, cfg.depth), W.VBox(derived), grand_total, submit])

    def one_action() -> tuple[int, bool]:
        before = fires["n"]
        inputs[0].value = 42.0
        return fires["n"] - before, False

    return root, edges, one_action


def _build_mvu(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    n = cfg.n_fields
    values = [0.0] * n
    inputs = [W.FloatText(value=0.0, description=f"f{i}") for i in range(n)]
    errors = [W.Label() for _ in range(n)]
    derived = [W.Label() for _ in range(cfg.chain)]
    grand_total = W.Label()
    submit = W.Button(description="submit")
    shared_legends = [W.HTML(value=f"help {i}") for i in range(cfg.shared)]

    fires = {"n": 0}
    syncing = {"flag": False}
    edges: list[tuple[str, str]] = [("event", "update"), ("update", "model")]

    def render() -> None:
        # pure projections of the model, one acyclic pass
        for k in range(n // 2):
            fires["n"] += 1
            a, b = 2 * k, 2 * k + 1
            errors[a].value = "" if values[a] <= values[b] else f"f{a} must be <= f{b}"
        prev = "0"
        for i in range(cfg.chain):
            fires["n"] += 1
            prev = f"d{i}({prev},{values[i % n]})"
            derived[i].value = prev
        fires["n"] += 1
        grand_total.value = f"total={sum(values)}"
        fires["n"] += 1
        submit.disabled = any(e.value for e in errors)
        syncing["flag"] = True
        try:
            for i, w in enumerate(inputs):
                if w.value != values[i]:
                    w.value = values[i]
        finally:
            syncing["flag"] = False

    def dispatch(i: int, v: float) -> None:
        if syncing["flag"]:
            return
        values[i] = v
        render()

    for i, w in enumerate(inputs):
        w.observe(lambda ch, i=i: dispatch(i, ch["new"]), names="value")
        edges.append((f"in{i}", "event"))
    for i in range(n):
        edges += [("model", f"err{i}")]
    for i in range(cfg.chain):
        edges.append(("model", f"d{i}"))
    edges += [("model", "total"), ("model", "submit")]

    render()

    rows = [W.VBox([inputs[i], errors[i], shared_legends[i % cfg.shared]]) for i in range(n)]
    root = W.VBox([_nest(rows, cfg.depth), W.VBox(derived), grand_total, submit])

    def one_action() -> tuple[int, bool]:
        before = fires["n"]
        dispatch(0, 42.0)
        return fires["n"] - before, False

    return root, edges, one_action


def _build_reactive(cfg: Config) -> tuple[Any, list[tuple[str, str]], Any]:
    """Variant C: a tracked reactive DAG — incremental like A, acyclic like B."""
    n = cfg.n_fields
    edges: list[tuple[str, str]] = []
    counter = {"n": 0}

    inputs = [W.FloatText(value=0.0, description=f"f{i}") for i in range(n)]
    errors = [W.Label() for _ in range(n)]
    derived = [W.Label() for _ in range(cfg.chain)]
    grand_total = W.Label()
    submit = W.Button(description="submit")
    shared_legends = [W.HTML(value=f"help {i}") for i in range(cfg.shared)]

    sig = [Signal(0.0, edges, name=f"in{i}") for i in range(n)]
    for i, w in enumerate(inputs):  # widget edit -> update the source signal
        w.observe(lambda ch, i=i: sig[i].set(ch["new"]), names="value")

    # cross-field validation errors as computeds; effects write them to labels
    err_computeds = []
    for k in range(n // 2):
        a, b = 2 * k, 2 * k + 1
        c = Computed(
            lambda a=a, b=b: "" if sig[a].get() <= sig[b].get() else f"f{a} must be <= f{b}",
            name=f"errc{k}", counter=counter, edges=edges,
        )
        err_computeds.append(c)
        Effect(
            lambda a=a, c=c: setattr(errors[a], "value", c.get()),
            name=f"err{a}", counter=counter,
        )

    # derived chain: each node depends only on the previous node + one input
    chain_computeds: list[Computed] = []
    for i in range(cfg.chain):
        def fn(i=i):
            prev = chain_computeds[i - 1].get() if i > 0 else "0"
            return f"d{i}({prev},{sig[i % n].get()})"

        c = Computed(fn, name=f"d{i}", counter=counter, edges=edges)
        chain_computeds.append(c)
        Effect(
            lambda i=i, c=c: setattr(derived[i], "value", c.get()),
            name=f"de{i}", counter=counter,
        )

    total_c = Computed(
        lambda: sum(s.get() for s in sig), name="total", counter=counter, edges=edges
    )
    Effect(
        lambda: setattr(grand_total, "value", f"total={total_c.get()}"),
        name="totale", counter=counter,
    )

    submit_c = Computed(
        lambda: any(c.get() for c in err_computeds), name="submitc", counter=counter, edges=edges
    )
    Effect(lambda: setattr(submit, "disabled", submit_c.get()), name="submite", counter=counter)

    rows = [W.VBox([inputs[i], errors[i], shared_legends[i % cfg.shared]]) for i in range(n)]
    root = W.VBox([_nest(rows, cfg.depth), W.VBox(derived), grand_total, submit])

    def one_action() -> tuple[int, bool]:
        before = counter["n"]
        sig[0].set(42.0)  # recomputes ONLY the downstream nodes
        return counter["n"] - before, False

    return root, edges, one_action
