# Plotje + cositos: a path to interactive plotting in Clojure

**Date:** 2026-07-14
**Source:** https://github.com/scicloj/plotje (alpha, MIT, Scicloj)
**Kind:** advisory investigation — integration opportunity, no code changes yet

## Key discovery: Plotje is built on membrane

Plotje's pipeline: **data → `plan` (malli-validated, serializable) → membrane UI
components → any membrane backend**. Evidence in the source tree:
`impl/plan_schema.clj`, `impl/pose_schema.clj`, and `impl/membrane.clj`
(docstring: a `PlotjeMembrane` "composes naturally with other Membrane
components and renders through any Membrane backend without special-casing").

The three projects form a natural stack:

- **Plotje** = Grammar of Graphics spec → plan → membrane components
- **Membrane** = platform-agnostic UI values + event model (desktop/terminal/WebGL)
- **cositos** = two-way browser↔REPL channel (ClayChannel over Clay's websocket)

## Why this matters for cositos

cositos' recommended Clojure host is Clay — and Plotje is Scicloj's plotting
library *for Clay* (Kindly-based). Today Plotje in Clay renders **static SVG**:
one-way, no events. Interactive plotting needs exactly what cositos already
provides — two-way `ClayChannel` (`broadcast!` + receive), the ESM `Model`,
and the `cositos.clay` codec with base64 buffers.

## Integration paths (in order of pragmatism)

### 1. SVG-embed + event round-trip (demo-scale, doable now)
- Render plot server-side via membrane's SVG backend.
- One cositos widget ESM module injects the SVG and attaches pointer listeners.
- Events (pixel coords) flow over `ClayChannel`; Clojure side maps pixel →
  data coordinates using plan scale metadata (`impl/scale.clj`, `impl/coord.clj`);
  REPL recomputes; new SVG pushed back via state sync.
- Missing pieces: one ESM module, a pixel→data mapping helper, a Kindly hook so
  Plotje results render as live widgets instead of static SVG.

### 2. Plan-as-spec (big win, bigger lift)
Plotje's `plan` schema is a serializable malli-validated IR — vega-lite-style
widget payload shape. A JS frontend interpreting plans directly would give
client-side rendering with hover/brush and no server round-trip per frame.
Blocked on the plan schema stabilizing (Plotje is alpha).

### 3. Non-Jupyter path (adjacent, no cositos needed)
Membrane's event model means Plotje could go interactive in a desktop/terminal
membrane backend today. Worth a docs mention; doesn't touch cositos.

## Honest constraints

- Plotje is alpha; path 1 insulates cositos from plan-schema churn, path 2
  should wait for schema stability.
- Pixel→data hit-testing is the fiddly part — but `impl/scale.clj` delegates to
  **wadogo** (`wadogo.scale`), an invertible scale lib (:linear/:log/:categorical),
  so pixel→data inversion comes for free. Confirmed 2026-07-14.
- Clay websocket frames are text-tagged (`cositos ` prefix); events are small
  JSON, so no buffer complications.

## Recommendation

Path 1 as a Clay demo (brushing line chart, counter-demo style). Doubles as
proof of the ClayChannel two-way story and a flagship docs example.

## Relations to other investigations

- `2026-08-28-what-cositos-can-learn-from-phronmophobic-membra.md` — membrane
  was investigated as an architectural sibling; Plotje turns out to be a
  membrane *consumer*, which makes the MembraneChannel idea and this
  integration converge on the same membrane event model.

