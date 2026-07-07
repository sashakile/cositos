# Widget-app state management: benchmark findings

Empirical study (`examples/benchmarks/`) of why large ipywidgets apps tangle, built to
ground the "how should cositos users manage complex state" design question. Same logical
app built three ways and measured.

## Variants
- **A naive** — peer-to-peer `observe`/`link` (idiomatic ipywidgets)
- **B MVU** — one Model, pure projections, single update pass
- **C reactive DAG** — tracked signals (`reactive.py`): reads record dependencies

## Findings (see `examples/benchmarks/RESULTS.md`, grounded as dont claims)
1. **The tangle is topology-specific, not size-specific.** Cross-filtering
   (cyclic/cross-writing) explodes to O(views*dims) edges and recomputes per action; pure
   fan-out (master-detail) is benign and near-identical between A and B. So *cycles and
   cross-writes* are the problem — not fan-out or scale.
2. **Peer links never survive static export** (`links_kept=0` everywhere): LinkModels live
   outside the container tree so the ipywidgets embed harvester never reaches them.
   Cross-part behavior must live in the *model* to be serializable.
3. **The MVU trade-off is real and not one-sided.** In the form scenario the update-storm
   *flips*: naive `observe` recomputes only the affected subgraph (incremental) while MVU
   re-renders the whole projection every edit (coarse). A reactive DAG (variant C) gets
   both — incremental recompute AND acyclicity/serializability.

## Complete results (storm = recomputes per action at `big` scale; A/B/C)

| Scenario | A naive | B MVU | C reactive DAG |
|----------|---------|-------|----------------|
| crossfilter | 1700, **cyclic** | 100, acyclic | 200, **acyclic** |
| masterdetail | 150, **cyclic** | 150, acyclic | 301, **acyclic** |
| form | 23, **cyclic** | 86, acyclic | 46, **acyclic** |

(C counts each Computed plus its Effect separately, so its per-node work is ~half the
listed number — on a per-affected-node basis C matches A's incrementality.)

**Consolidated conclusion.** Across all three topologies: A is always cyclic (needs guards,
risks loops, never serializes its links); B is always acyclic but recomputes the whole
projection; C is always acyclic and never loses — it *wins* where an incremental subgraph
exists (form: 46 vs 86) and *ties* B where dependencies are genuinely dense
(crossfilter/masterdetail), while always removing A's cyclic explosion.

## Design implication for cositos
Recommend a documented discipline (not a runtime in the pure core): one domain Model as the
single source of truth; views as projections; cross-part behavior through the model or a
tracked DAG, never peer `link`/`observe`. This is what keeps apps acyclic AND serializable.

## Related
- Reuse question: do NOT reimplement anywidget's descriptor in Python — depend on it (still
  experimental but current; RFC 0001 extends it). Reimplementation only matters for
  non-Python backends, and then as a portable contract.
- Open cositos bug surfaced separately: load_document mutates its input (beads cositos-t3c).
- Env gotcha: `uv sync` without `--extra oracle` prunes ipywidgets from the venv.

