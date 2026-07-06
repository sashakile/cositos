## Why

cositos can shape and parse live widget messages, but it cannot **save a widget's status
to a file and rebuild it later**. Users want to snapshot a whole UI (including composed,
nested widgets and their binary data) to JSON and reconstruct it. ipywidgets already
defines the exact on-disk format for this — the Widget State JSON schema v2
(`application/vnd.jupyter.widget-state+json`) — and its canonical producer is built on the
same `remove_buffers`/`put_buffers` primitives cositos already owns. Reusing that format
(rather than inventing one) keeps cositos binding-free, gives ecosystem interop, and lets
every language port certify against one golden fixture like the rest of the project.

## What Changes

- Add pure serialization functions to the core: `dump_model`/`load_model` (one widget) and
  `dump_document`/`load_document` (a multi-widget, composed UI), producing/consuming the
  v2 `widget-state+json` envelope with base64-encoded binary buffers.
- Introduce named boundary types so the round-trip is a checkable law: `ModelEntry`
  `(model_id, state)`, `Document` (the v2 envelope), and a pure
  `encode_buffers_base64`/`decode_buffers_base64` step over the `remove_buffers` triple.
- Enforce that every serialized model has a **non-empty, unique `model_id`** (the document
  primary key); reject otherwise at the boundary.
- Composition is covered for free: children stored as `"IPY_MODEL_<id>"` reference strings
  round-trip as ordinary state — no new mechanism.
- Add a golden fixture `fixtures/widget-state.json` (a composed UI with a child ref and a
  float32 array buffer) as the cross-language contract.

### Non-breaking / non-goals

This change is **additive only** — no existing signatures change. Explicitly out of scope:

- **`Message` sum type / builder refactor.** Reconstruction (Option A) rebuilds host
  objects and calls `Widget.open()` normally; it does *not* replay a message list, so a
  common outbound `Message` type is not needed here. It belongs with the deferred
  reconciler, not this change.
- **Rich-type codecs** (numpy/pandas ↔ bytes). The core stays byte-oriented; float arrays
  already round-trip as `memoryview` + `dtype`/`shape` state. Codecs are a per-language
  layer above the core.
- **Elm/reconciler app layer** and **auto-generated UIs** (see the design's "Explored, not
  committed" section).

## Capabilities

### New Capabilities
- `serialization`: saving widget state to, and reconstructing it from, the ipywidgets
  Widget State JSON schema v2 — including composed widget graphs and binary buffers.

### Modified Capabilities
<!-- None. This change is additive; existing protocol/buffer requirements are unchanged. -->

## Impact

- **Code:** new `src/cositos/serialize.py`; re-exports from `src/cositos/__init__.py`.
  No changes to `protocol.py`, `buffers.py`, `transport.py`, or `model.py`.
- **Contract:** new `fixtures/widget-state.json`; the committed scope certifies the Python
  core round-trip. Front-end/other-language conformance can consume the same fixture later.
- **Dependencies:** none new (`base64` is stdlib).
- **Docs:** `docs/porting.md` gains a serialization round-trip certification note.
