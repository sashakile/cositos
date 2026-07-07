# Widget-app state management: benchmark findings

Empirical study (`examples/benchmarks/`) of why large ipywidgets apps tangle, built to
ground the "how should cositos users manage complex state" design question. Same logical
app built three ways and measured.

## Variants
- **A naive** — peer-to-peer `observe`/`link` (idiomatic ipywidgets)
- **B MVU** — one Model, pure projections, single update pass
- **C reactive DAG** — tracked signals (`reactive.py`): reads record dependencies
- **D reactive + shared memo** — crossfilter only: the expensive scan is one shared Computed

## Metric definitions (amnesia-proof)
- **storm** — output refreshes (widget updates) caused by one user action; counted the same
  way in every variant (one unit per output write), so A/B/C/D are directly comparable.
- **scans** — expensive O(rows) recomputations for that action; a cost proxy the refresh
  count hides.
- **data_edges / acyclic** — size and cyclicity of the *declared* data-flow graph.
- **links_kept** — peer LinkModels surviving into the serialized document.

Grounded dont claims: claim:01KWX49WFJ1F31348M12R2S93E (topology-specific tangle),
claim:01KWX4FFJF1568ZBWH5D52XP6G (links unserializable),
claim:01KWX4ES0FR9HW0VWX724E28KC (reactive DAG incremental and acyclic).

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

## Complete results (storm = output refreshes, scans = O(rows) recomputes, at `big` scale)

| Scenario | A naive | B MVU | C reactive | D shared-reactive |
|----------|---------|-------|------------|-------------------|
| crossfilter | storm 1700 scans 1700, **cyclic** | storm 100 scans 1, acyclic | storm 100 scans 100, acyclic | storm 100 scans 1, acyclic |
| masterdetail | storm 150, **cyclic** | storm 150, acyclic | storm 151, acyclic | — |
| form | storm 23, **cyclic** | storm 86, acyclic | storm 23, acyclic | — |
| dynamic (add rows) | created 60 storm 1, acyclic | created 360 storm 120, acyclic | created 60 storm 1, acyclic | — |

Measured `obs` (real traitlets change-handlers) corroborates the declared edges: crossfilter
big A=2750 vs B=466, confirming the peer-wiring tangle is real, not a modelling artifact.

**Consolidated conclusion (corrected after Rule-of-5 review).**
- A is cyclic under cross-writes (needs guards, never serializes its links) and
  catastrophic on cost there (1700 scans for one action). But naive is *not* inherently
  cyclic — the dynamic scenario's fan-in A is acyclic; cross-writes are the hazard.
- B is always acyclic and cheap for value changes (shares the scan), but its
  whole-projection rebuild pays O(N) reconciliation cost for **structural** changes
  (dynamic: rebuilds all 360 widgets to add 20).
- C matches A's incrementality on the form (storm 23) and on dynamic structure (created 60)
  while staying acyclic. But on cross-filter C does one O(rows) scan **per view**
  (scans=100) — fine-grained reactivity does not share derivations for free.
- D (reactive + shared memoized Computed) restores scans=1, tying B on cost.

So no single style wins everywhere: cross-writes favour any acyclic model; value-heavy work
favours reactive/shared; structural churn favours incremental/reactive over rebuild-MVU.

## Design implication for cositos
Recommend a documented discipline (not a runtime in the pure core): one domain Model as the
single source of truth; views as projections; cross-part behavior through the model or a
tracked DAG with **shared derivations**, never peer `link`/`observe`. This keeps apps
acyclic, serializable, AND cheap.

## Known limitations of this study (Rule-of-5 review; some now addressed)
- `data_edges` and cyclicity come from the *declared* edge list, but a *measured* `obs`
  (real traitlets change-handlers) now corroborates wiring density (CORR-002 addressed for
  magnitude; cyclicity remains a model property).
- Variant A is engineered to expose the tangle (write-back cycles + link clique) — a
  plausible-worst-case, not a measured-typical, baseline. *(open)*
- `scans`/`created` are cost proxies; no wall-clock timing was taken. *(open)*
- Dynamic structure is now covered by the `dynamic` scenario and it flips the MVU verdict
  (EDGE-001 addressed).
- `reactive.py` is now glitch-free (mark-and-pull, memoized) with a cycle guard, proven by
  `reactive_selftest.py` (CORR-003/EXCL-003 addressed).

## Related
- Reuse question: do NOT reimplement anywidget's descriptor in Python — depend on it (still
  experimental but current; RFC 0001 extends it). Reimplementation only matters for
  non-Python backends, and then as a portable contract.
- Open cositos bug surfaced separately: load_document mutates its input (beads cositos-t3c).
- Env gotcha: `uv sync` without `--extra oracle` prunes ipywidgets from the venv.

