## Context

cositos is a binding-free anywidget/ipywidgets protocol core. It can shape and parse live
comm messages and split/merge binary buffers, but has no persistence. The fuller design
trail (layered architecture, Elm/auto-view exploration, YAGNI trimming, composability
review) lives at
`.wai/projects/cositos-core/designs/2026-07-06-design-serializable-widgets-composition-and-a.md`;
this file records only the decisions binding on the committed `serialization` capability.

## Goals / Non-Goals

**Goals:**
- Lossless save/restore of widget state (JSON values + binary buffers) via the stock
  ipywidgets Widget State JSON schema v2 — no new format invented.
- Reconstruct composed, nested UIs from one document.
- Make the round-trip a checkable algebraic law.

**Non-Goals:**
- `Message` sum type / builder refactor (only the deferred reconciler needs it).
- Rich-type codecs (numpy/pandas ↔ bytes).
- Elm/reconciler app layer; auto-generated UIs.

## Decisions

- **Reuse schema v2, don't invent.** Mirror ipywidgets `serialize_state`
  (`ipywidgets/packages/base-manager/src/manager-base.ts:884`) so bytes match and the
  fixture is a genuine cross-language contract. Record = `{model_name, model_module,
  model_module_version?, state, buffers?}`; envelope = `{version_major:2, version_minor:0,
  state:{id: record}}`. **State-format version 2.0 ≠ protocol version 2.1.0** — kept
  distinct.
- **Reconstruction API = pure functions (Option A).** The host rebuilds its own objects
  from loaded dicts and calls `Widget.open()`; the core adds no state-owning layer. This
  is *why* no `Message` type is needed: reconstruction replays nothing.
- **Named boundary types.** `ModelEntry (model_id, state)` and `Document` give the
  round-trip law shared endpoints; `dump`/`load` form an inverse pair on them.
- **Buffers: base64, compared by raw bytes.** ipywidgets compares buffers via
  `memoryview(x).cast('B')` (`.../widgets/widget.py:147-167`) because a `float32`
  memoryview ≠ a plain-bytes memoryview with identical bytes. All round-trip/PBT buffer
  comparisons use raw bytes, or float-array fixtures fail spuriously.
- **Composition is free.** `"IPY_MODEL_<id>"` refs are ordinary strings in state; they
  round-trip with no new mechanism, and load-by-id-lookup makes reference cycles safe.
- **`model_id` validated at the boundary** (non-empty, unique) since it is the document
  primary key; `Widget.model_id` currently defaults to `""` (`src/cositos/model.py`).

## Risks / Trade-offs

- **Self-contained vs. size.** Inlining `_esm`/`_css` per model makes documents portable
  but larger when many widgets share code. Accepted for v0 (matches ipywidgets);
  de-duplication deferred.
- **Byte-exactness with the reference producer** depends on key ordering / base64 padding
  matching ipywidgets. Mitigated by certifying against `fixtures/widget-state.json` rather
  than asserting a hand-written string.
- **Rich payloads today.** Without codecs, hosts must hand a `memoryview` + `dtype`/`shape`
  themselves; ergonomic wrappers are a later, per-language layer.
