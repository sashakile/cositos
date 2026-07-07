"""Shared, scenario-agnostic benchmark library.

Each *scenario* module (e.g. ``crossfilter``, ``masterdetail``) exposes:

* ``SCALES: dict[str, Config]`` — named sizes, where ``Config`` has a ``.label``
* ``build(variant: str, scale: str) -> (root, edges, one_action)`` where
  ``variant`` is ``"A"`` (naive peer-to-peer) or ``"B"`` (MVU single-model),
  ``root`` is the ipywidgets root, ``edges`` is the declared data-flow edge list, and
  ``one_action() -> (recomputes: int, needed_guard: bool, scans: int, created: int)``
  performs one user action, returning the output-refresh count, whether a re-entrancy guard
  fired, the number of expensive O(rows) recomputations, and the number of widgets
  constructed (reconciliation cost, which dominates dynamic-structure scenarios).

This module owns the metrics: widget-tree shape, data-flow acyclicity, update-storm size,
and whether the tree survives ``cositos`` serialize -> static embed.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Any, Protocol

#: Default fresh-rebuild repeats when timing is requested (median resists scheduler noise).
TIMING_REPEATS = 7


class Scenario(Protocol):
    SCALES: dict[str, Any]

    def build(self, variant: str, scale: str) -> tuple[Any, list[tuple[str, str]], Any]: ...


@dataclass
class Metrics:
    scenario: str
    variant: str
    scale: str
    n_widgets: int
    max_depth: int
    n_shared: int  # widgets referenced by >1 parent (repeated widgets)
    n_data_edges: int  # observe/link dependency edges (declared by the builder)
    observers: int  # REAL traitlets change-handlers on the widget tree (measured)
    data_flow_acyclic: bool
    recomputes_per_action: int  # "update storm": output refreshes for one user action
    scans_per_action: int  # expensive O(rows) recomputations for one action (cost proxy)
    created_per_action: int  # widgets constructed for one action (reconciliation cost)
    needed_reentrancy_guard: bool
    serialize_ok: bool
    n_models: int
    n_link_models: int  # LinkModels that survived into the serialized document
    action_ms: float | None = None  # median wall-clock of one_action() (None = not timed)

    def row(self) -> str:
        cyc = "acyclic" if self.data_flow_acyclic else "HAS CYCLE"
        guard = " (guarded)" if self.needed_reentrancy_guard else ""
        ser = f"{self.n_models} models" if self.serialize_ok else "FAILED"
        timing = "" if self.action_ms is None else f" t={self.action_ms:.3f}ms"
        return (
            f"{self.variant:<6} | widgets={self.n_widgets:<5} depth={self.max_depth:<2} "
            f"shared={self.n_shared:<3} | edges={self.n_data_edges:<5} obs={self.observers:<5} "
            f"{cyc:<9} | storm={self.recomputes_per_action:<5}{guard} "
            f"scans={self.scans_per_action:<4} created={self.created_per_action:<5}{timing} | "
            f"{ser}, links_kept={self.n_link_models}"
        )


def containment_stats(root: Any) -> tuple[int, int, int]:
    """Return ``(n_widgets, max_depth, n_shared)`` for an ipywidgets ``.children`` tree.

    A widget reached via >1 parent counts as shared (a repeated widget). Depth is the
    longest root->leaf containment path.
    """
    parents: dict[int, int] = {}
    max_depth = 0
    seen: set[int] = set()

    def walk(w: Any, depth: int) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        seen.add(id(w))
        for c in getattr(w, "children", ()) or ():
            parents[id(c)] = parents.get(id(c), 0) + 1
            if id(c) not in seen:
                walk(c, depth + 1)

    walk(root, 0)
    n_shared = sum(1 for cnt in parents.values() if cnt > 1)
    return len(seen), max_depth, n_shared


def _collect_widgets(root: Any) -> list[Any]:
    """All distinct widgets reachable via ``.children`` from ``root``."""
    seen: dict[int, Any] = {}

    def walk(w: Any) -> None:
        if id(w) in seen:
            return
        seen[id(w)] = w
        for c in getattr(w, "children", ()) or ():
            walk(c)

    walk(root)
    return list(seen.values())


def count_observers(root: Any) -> int:
    """MEASURED wiring: total traitlets ``change`` handlers across the widget tree.

    Unlike ``data_edges`` (declared by each builder) this reads the real observer registry
    (``_trait_notifiers``), so it is an objective corroboration of wiring density. Link
    widgets register their handlers on the in-tree source/target widgets, so peer links are
    counted here even though the Link widgets themselves float outside the tree.
    """
    total = 0
    for w in _collect_widgets(root):
        notifiers = getattr(w, "_trait_notifiers", {}) or {}
        for by_type in notifiers.values():
            total += len(by_type.get("change", []))
    return total


def is_acyclic(edges: list[tuple[Any, Any]]) -> bool:
    """DFS cycle check over a directed edge list of hashable node keys."""
    adj: dict[Any, list[Any]] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, [])
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(adj, WHITE)

    def dfs(u: Any) -> bool:
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                return False
            if color[v] == WHITE and not dfs(v):
                return False
        color[u] = BLACK
        return True

    return all(color[u] != WHITE or dfs(u) for u in list(adj))


def serialize_check(root: Any) -> tuple[bool, int, int]:
    """Harvest the widget tree via ipywidgets, then embed it with cositos.

    Returns ``(ok, n_models, n_link_models)``. Uses the non-deprecated ``embed_data``
    walker, whose ``manager_state`` is exactly a cositos Document. ``n_link_models``
    counts surviving ``LinkModel`` widgets — peer links live outside the container tree,
    so they are dropped.
    """
    try:
        from ipywidgets.embed import embed_data

        from cositos.embed import embed_html

        doc = embed_data(views=[root])["manager_state"]
        state = doc.get("state", {})
        embed_html(doc, views=[getattr(root, "model_id", None)])
        n_links = sum(1 for r in state.values() if r.get("model_name") == "LinkModel")
        return True, len(state), n_links
    except Exception:  # noqa: BLE001
        return False, 0, 0


def time_action(module: Any, variant: str, scale: str, repeats: int) -> float:
    """Median wall-clock (ms) of one ``one_action()``, each on a **fresh** build.

    Actions are not idempotent (crossfilter re-sets the same value → no re-fire; dynamic
    appends rows), so a repeated action on one build would not represent "one action".
    We therefore rebuild before every timed action and exclude build time from the clock,
    isolating the latency of the user action itself. The median resists scheduler noise.
    """
    samples: list[float] = []
    for _ in range(repeats):
        _root, _edges, one_action = module.build(variant, scale)
        start = time.perf_counter()
        one_action()
        samples.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(samples)


def measure(
    scenario_name: str, module: Any, variant: str, scale: str, timing_repeats: int = 0
) -> Metrics:
    """Build one (scenario, variant, scale) and compute its metrics. Run in a subprocess:
    ipywidgets' global widget registry cross-contaminates sequential builds otherwise.

    When ``timing_repeats > 0`` also records ``action_ms`` (median wall-clock of the user
    action over that many fresh rebuilds) so cost claims rest on latency, not just counts."""
    root, edges, one_action = module.build(variant, scale)
    n_widgets, max_depth, n_shared = containment_stats(root)
    observers = count_observers(root)
    storm, needed_guard, scans, created = one_action()
    edges = list(dict.fromkeys(edges))  # dedupe (tracked reactive reads re-record edges)
    ok, n_models, n_links = serialize_check(root)
    action_ms = time_action(module, variant, scale, timing_repeats) if timing_repeats else None
    return Metrics(
        scenario=scenario_name,
        variant=variant,
        scale=scale,
        n_widgets=n_widgets,
        max_depth=max_depth,
        n_shared=n_shared,
        n_data_edges=len(edges),
        observers=observers,
        data_flow_acyclic=is_acyclic(edges),
        recomputes_per_action=storm,
        scans_per_action=scans,
        created_per_action=created,
        needed_reentrancy_guard=needed_guard,
        serialize_ok=ok,
        n_models=n_models,
        n_link_models=n_links,
        action_ms=action_ms,
    )
