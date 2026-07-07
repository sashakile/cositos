# Widget-app structure benchmarks

**Purpose.** Make concrete — with numbers, not assertions — *why large widget apps
tangle*, and which app topologies actually cause it. Each **scenario** builds the *same*
logical app two ways and measures the structural cost:

- **variant A (naive)** — real ipywidgets wired **peer-to-peer** with `observe`/`link`
  (the idiomatic style).
- **variant B (MVU)** — one domain `Model`; a user action is one `update`; views are
  **pure projections** re-rendered in a single pass.
- **variant C (reactive DAG)** — a tracked signal graph (`reactive.py`): reading a value
  inside a computation records a dependency, so one edit recomputes *only* the downstream
  nodes, and the graph is acyclic by construction. Wired for all scenarios; scenarios opt
  in via a `VARIANTS` attribute.
- **variant D (reactive + shared memo)** — crossfilter only: like C but the expensive scan
  is a single shared `Computed` all views read, so the O(rows) work runs once per action
  instead of once per view.

The *rendered* widget tree (deep nesting, many elements, shared/repeated widgets) is the
same in both — only the **wiring** differs — so serialization is apples-to-apples.

## Run

```bash
# env with ipywidgets + cositos (extras: oracle)
python examples/benchmarks/run.py                 # all scenarios, all scales
python examples/benchmarks/run.py crossfilter big
```

Each `(scenario, variant, scale)` runs in a **fresh subprocess**: ipywidgets keeps a
global widget registry that cross-contaminates sequential harvests otherwise. Output goes
to `RESULTS.md`.

## Files

- `benchlib.py` — scenario-agnostic metrics: tree shape, data-flow acyclicity, update-storm
  size, and the `cositos` serialize→embed check. Defines the scenario contract.
- `crossfilter.py` — scenario: filters + many views that cross-filter each other.
- `masterdetail.py` — scenario: one selection drives many detail views; several master
  controls kept in sync.
- `form.py` — scenario: validated form with a derived-field chain, a grand-total fan-in,
  cross-field validation, and a submit gate.
- `run.py` — subprocess-isolated runner.

A scenario module exposes `SCALES: dict[str, Config]` and
`build(variant, scale) -> (root, edges, one_action)`, where `one_action()` performs one
user action and returns `(recomputes, needed_guard)`.

## Metrics

| Metric | Meaning |
|---|---|
| `widgets`/`depth`/`shared` | tree size, nesting depth, repeated (multi-parent) widgets |
| `data_edges` | declared `observe`/`link` dependency edges — the wiring complexity |
| `acyclic`/`HAS CYCLE` | whether the data-flow graph has a cycle (cycles need re-entrancy guards and risk infinite update loops) |
| `storm` | output refreshes (widget updates) triggered by **one** user action — one unit across variants |
| `scans` | expensive O(rows) recomputations for that action; a cost proxy the refresh count hides |
| `models` | widgets in the serialized `cositos` document (`ipywidgets.embed.embed_data` → `cositos.embed_html`) |
| `links_kept` | cross-part `LinkModel`s that survive into the serialized document |

## What the results show (`RESULTS.md`)

**Cross-filter (bidirectional / cyclic) is where it explodes.** At `big` (16 dims, 100
views):

- wiring: A = 1900 edges (≈ views×dims) vs B = 118 (≈ views) — super-linear vs linear;
- one click: A = 1700 refreshes vs B = 100 (a single projection pass);
- A's data-flow graph is **always cyclic**, B's never is.

**The `scans` metric corrects a naive reading of C.** On refresh *count* C matches B
(100 = 100), but C runs the O(rows) scan **once per view** (`scans=100`) while B scans
**once** (`scans=1`): the count hid V-to-1 redundant work. Variant **D** (shared memoized
`Computed`) scans **once** (`scans=1`), truly tying B. And A scans **1700** times — every
cascaded recompute rescans, so it is catastrophic on cost, not just count. Lesson: fine-
grained reactivity needs *shared* derivations to match a well-written MVU render; it does
not get that for free.

**Master-detail (pure fan-out) is benign — an important contrast.** A and B come out nearly
identical (`storm` equal; `data_edges` differ only by the master clique). Fan-out alone
does *not* tangle: the only pathology is the linked-master **clique**, which makes A cyclic
(and is O(masters²)) while B stays acyclic by reading one model. So the lesson is precise:
**cycles and cross-writes are the problem, not size or fan-out.**

**Peer links never survive static export (`links_kept=0`, all scenarios, even variant A).**
`LinkModel`s live outside the container tree, so the harvester never sees them — the
interactive cross-part behavior is silently lost in a saved/embedded page. In variant B the
cross-part behavior is a model update, so the resulting *state* serializes fine.

**Form (derived state + validation) exposes the real trade-off — and it is not one-sided.**
Here the `storm` metric *flips*: at `big` (128 fields, chain 20) variant A recomputes only
**23** callbacks per edit while variant B recomputes **86**. Fine-grained `observe` wiring
recomputes *exactly the affected subgraph* (precise, incremental), whereas the MVU version
re-renders the *whole* model projection every edit (coarse, but simple and acyclic). So the
naive style is not simply "worse": it buys incremental recomputation at the cost of a
cyclic, unserializable dependency web.

**Variant C (reactive DAG) is the best of both.** At `big`, C refreshes **23** — exactly
variant A's incremental count (only the affected subgraph) — and is **acyclic** with a
single source of truth. It gets A's incrementality *and* B's acyclicity/serializability.
This is the concrete argument for a tracked dependency graph over both peer `observe` and
whole-model re-render.

### cositos findings surfaced

1. **Positive:** deeply nested trees with shared/repeated widgets harvest + embed cleanly
   (shared widgets round-trip as `IPY_MODEL_` refs — no duplication, no failure).
2. **Limitation (not a bug):** peer-`link` interaction is unserializable by construction —
   direct evidence for the guideline that cross-part behavior belongs in the **model**, not
   in widget-to-widget links.

## Takeaway

The tangle is measurable and topology-specific: **cyclic/cross-writing wiring is O(V×D)
edges with O(V×D) refreshes *and* O(V×D) expensive scans, and does not serialize; a
single-model projection is O(V) acyclic with a single scan.** Fan-out and sheer size are
fine. The form scenario shows MVU's simplicity costs coarse re-rendering, which a reactive
DAG (C) fixes — but the `scans` metric shows reactivity only matches MVU's *cost* when it
shares derivations (variant D), not by default. Together this is the concrete basis for the
"impose one directed boundary (single Model / tracked DAG with shared derivations)"
guideline.
