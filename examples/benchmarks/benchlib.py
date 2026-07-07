"""Shared, scenario-agnostic benchmark library.

Each *scenario* module (e.g. ``crossfilter``, ``masterdetail``) exposes:

* ``SCALES: dict[str, Config]`` — named sizes, where ``Config`` has a ``.label``
* ``build(variant: str, scale: str) -> (root, edges, one_action)`` where
  ``variant`` is ``"A"`` (naive peer-to-peer) or ``"B"`` (MVU single-model),
  ``root`` is the ipywidgets root, ``edges`` is the declared data-flow edge list, and
  ``one_action() -> (recomputes: int, needed_guard: bool)`` performs one user action.

This module owns the metrics: widget-tree shape, data-flow acyclicity, update-storm size,
and whether the tree survives ``cositos`` serialize -> static embed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


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
    n_data_edges: int  # observe/link dependency edges
    data_flow_acyclic: bool
    recomputes_per_action: int  # "update storm" size for one user action
    needed_reentrancy_guard: bool
    serialize_ok: bool
    n_models: int
    n_link_models: int  # LinkModels that survived into the serialized document

    def row(self) -> str:
        cyc = "acyclic" if self.data_flow_acyclic else "HAS CYCLE"
        guard = " (guarded)" if self.needed_reentrancy_guard else ""
        ser = f"{self.n_models} models" if self.serialize_ok else "FAILED"
        return (
            f"{self.variant:<6} | widgets={self.n_widgets:<5} depth={self.max_depth:<2} "
            f"shared={self.n_shared:<3} | data_edges={self.n_data_edges:<5} {cyc:<9} | "
            f"storm={self.recomputes_per_action:<5}{guard} | {ser}, links_kept={self.n_link_models}"
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


def measure(scenario_name: str, module: Any, variant: str, scale: str) -> Metrics:
    """Build one (scenario, variant, scale) and compute its metrics. Run in a subprocess:
    ipywidgets' global widget registry cross-contaminates sequential builds otherwise."""
    root, edges, one_action = module.build(variant, scale)
    n_widgets, max_depth, n_shared = containment_stats(root)
    storm, needed_guard = one_action()
    edges = list(dict.fromkeys(edges))  # dedupe (tracked reactive reads re-record edges)
    ok, n_models, n_links = serialize_check(root)
    return Metrics(
        scenario=scenario_name, variant=variant, scale=scale, n_widgets=n_widgets,
        max_depth=max_depth, n_shared=n_shared, n_data_edges=len(edges),
        data_flow_acyclic=is_acyclic(edges), recomputes_per_action=storm,
        needed_reentrancy_guard=needed_guard, serialize_ok=ok, n_models=n_models,
        n_link_models=n_links,
    )
