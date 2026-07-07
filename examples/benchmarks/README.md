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
python examples/benchmarks/run.py all all --timing # + wall-clock per action (slower)
```

Each `(scenario, variant, scale)` runs in a **fresh subprocess**: ipywidgets keeps a
global widget registry that cross-contaminates sequential harvests otherwise. Output goes
to `RESULTS.md`. `--timing` adds a median wall-clock per user action (over fresh rebuilds),
so the cost story rests on latency, not just counts.

## Is variant A a fair baseline?

Variant A is the **idiomatic** ipywidgets style, not an engineered strawman: it wires
widgets to each other with `observe`, `link`, and `jslink` — the very APIs ipywidgets ships
and its tutorials teach for keeping widgets in sync. The *same* idiom is applied unchanged
in every scenario; only the app **topology** differs. That is what makes the comparison
fair, and the results prove the harness is not rigged to always favour B:

- **master-detail (fan-out): A ≈ B** — nearly identical `storm` and sub-millisecond latency
  in both. Peer wiring is *fine* here.
- **form (derived chain): A is actually cheaper on count** — incremental `observe`
  recomputes only the affected subgraph (`storm=23`) versus MVU's whole-projection rebuild
  (`storm=86`); latency is tiny for both.
- **cross-filter (bidirectional/cyclic): A explodes** — and only here.

So A wins, ties, or loses purely as a function of topology. The one honest caveat:
cross-filter A wires a *fully-connected* cross-filter (every view cross-writes every
dimension). That is the realistic shape of a cross-filter dashboard — and the finding is
precisely that this common, idiomatically-wired pattern is the hazard, not that the wiring
was contrived to fail.

## Files

- `benchlib.py` — scenario-agnostic metrics: tree shape, data-flow acyclicity, update-storm
  size, and the `cositos` serialize→embed check. Defines the scenario contract.
- `crossfilter.py` — scenario: filters + many views that cross-filter each other.
- `masterdetail.py` — scenario: one selection drives many detail views; several master
  controls kept in sync.
- `form.py` — scenario: validated form with a derived-field chain, a grand-total fan-in,
  cross-field validation, and a submit gate.
- `dynamic.py` — scenario: a variable-length list of rows; one action *adds* rows
  (structural change, not just value change).
- `reactive.py` — the glitch-free tracked-signal core; `reactive_selftest.py` proves
  diamond-recompute-once and cycle detection.
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
| `edges` / `obs` | *declared* dependency edges vs *measured* traitlets change-handlers on the tree (`obs` corroborates `edges` from the real observer registry) |
| `acyclic`/`HAS CYCLE` | whether the declared data-flow graph has a cycle (cycles need re-entrancy guards and risk infinite update loops) |
| `storm` | output refreshes (widget updates) triggered by **one** user action — one unit across variants |
| `scans` | expensive O(rows) recomputations for that action; a cost proxy the refresh count hides |
| `created` | widgets constructed for that action — reconciliation cost (dominates dynamic structure) |
| `t` | median wall-clock of **one** user action over fresh rebuilds (only with `--timing`) — latency backing for the `scans`/`created` proxies |
| `models` | widgets in the serialized `cositos` document (`ipywidgets.embed.embed_data` → `cositos.embed_html`) |
| `links_kept` | cross-part `LinkModel`s that survive into the serialized document |

## What the results show (`RESULTS.md`)

**Cross-filter (bidirectional / cyclic) is where it explodes.** At `big` (16 dims, 100
views):

- wiring: A = 1900 edges (≈ views×dims) vs B = 118 (≈ views) — super-linear vs linear;
- one click: A = 1700 refreshes vs B = 100 (a single projection pass);
- **wall-clock: A ≈ 2.7 s per click vs B ≈ 1.7 ms** (`--timing`, big) — a ~1600× latency
  gap, so "explodes" is literal, not rhetorical; at medium it is already A ≈ 88 ms vs
  B ≈ 0.4 ms;
- A's data-flow graph is **always cyclic**, B's never is.

**The `scans` metric corrects a naive reading of C.** On refresh *count* C matches B
(100 = 100), but C runs the O(rows) scan **once per view** (`scans=100`) while B scans
**once** (`scans=1`): the count hid V-to-1 redundant work. Variant **D** (shared memoized
`Computed`) scans **once** (`scans=1`), truly tying B. And A scans **1700** times — every
cascaded recompute rescans, so it is catastrophic on cost, not just count. Latency confirms
the ordering directly: at `big`, D ≈ 1.8 ms ≈ B ≈ 1.7 ms ≪ C ≈ 142 ms ≪ A ≈ 2.7 s. Lesson:
fine-grained reactivity needs *shared* derivations to match a well-written MVU render; it
does not get that for free.

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

**Dynamic structure flips the verdict on MVU.** Adding 20 rows to a 100-row list
(`dynamic` big): A and C construct only the new rows (`created=60`, `storm=1`), but B
re-renders the children list from the model, **rebuilding every row** (`created=360`,
`storm=120`) — and the orphaned widgets inflate its serialized document (1827 vs 1027
models). Latency makes the reconciliation cost concrete: B ≈ 30 ms vs A/C ≈ 5 ms (~6×).
MVU's whole-projection rebuild is fine for value changes but pays O(N) reconciliation cost
for structural ones (the reason React has keys/a vdom). Incremental and reactive styles
stay O(churn). Note A here is *acyclic* — pure fan-in, no cross-writes — confirming again
that cycles, not naivety per se, are the hazard.

## Takeaway

The tangle is measurable and topology-specific: **cyclic/cross-writing wiring is O(V×D)
edges with O(V×D) refreshes *and* O(V×D) expensive scans, and does not serialize; a
single-model projection is O(V) acyclic with a single scan.** Fan-out and sheer size are
fine. The form scenario shows MVU's simplicity costs coarse re-rendering, which a reactive
DAG (C) fixes — but the `scans` metric shows reactivity only matches MVU's *cost* when it
shares derivations (variant D), not by default. Together this is the concrete basis for the
"impose one directed boundary (single Model / tracked DAG with shared derivations)"
guideline.
