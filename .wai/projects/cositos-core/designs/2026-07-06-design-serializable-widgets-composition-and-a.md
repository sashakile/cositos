# Design: Serializable widgets (with composition), and a deferred app layer

## Goal
Make every cositos widget **serializable to (and reconstructable from) a JSON file**.
Because ipywidgets composition is already stateless, the same representation also lets you
**build complex components by nesting simpler ones** at no extra cost. Two further
capabilities the user raised — an Elm-style app layer and auto-generated UIs — are
*explored but explicitly not committed* below (see "Explored, not committed"), per YAGNI.

## Grounding: don't invent a format

cositos's charter is "reuse the ecosystem verbatim, keep the core binding-free." Two
existing facts anchor the design:

- **State schema exists.** ipywidgets `serialize_state`
  (`ipywidgets/packages/base-manager/src/manager-base.ts:884`) already produces exactly
  the save format we want, and it is built on the *same* `remove_buffers` / `put_buffers`
  primitives cositos already owns (`src/cositos/buffers.py`). Binary buffers become
  `{path, encoding:"base64", data}` records per model; the envelope is
  `{version_major:2, version_minor:0, state:{…}}`, mimetype
  `application/vnd.jupyter.widget-state+json`. The schema requires only
  `model_name, model_module, state` per record (`model_module_version` and `buffers` are
  optional; `ipywidgets/packages/schema/v2/state.schema.json`).
  - **Version subtlety:** the state-format version is `2.0`, distinct from the *protocol*
    version `2.1.0` that `protocol.py` already emits. Two version numbers, easily
    conflated — the design keeps them separate.
- **Composition is already stateless.** A container stores its children as
  `"IPY_MODEL_<id>"` strings inside its own `state`
  (`ipywidgets/python/ipywidgets/ipywidgets/widgets/widget.py:48-63`, `_widget_to_json` /
  `_json_to_widget`). So a saved document is **already a reference graph of widgets** —
  composition needs **no new primitive and no new code**; it falls out of serialization.

Targeting the stock schema means a saved cositos file *should* also load into the ordinary
ipywidgets embed manager (provided the anywidget frontend module is resolvable there —
untested, not relied on), and every language port certifies against the same golden
fixtures as the rest of cositos.

## Committed scope: serialization + composition

### Named types first (composability foundation)

The round-trip law `load ∘ dump = id` can only be *stated* if its endpoints share a type.
So name the boundary types before writing any encoder:

- **`ModelEntry = (model_id: str, state: dict)`** — one in-memory model. `dump`/`load`
  operate on this, giving a clean inverse pair `ModelEntry ⇄ Record`.
- **`Document`** — the v2 envelope: `{version_major:2, version_minor:0, state: {model_id:
  Record}}`, where `Record = {model_name, model_module, model_module_version?, state,
  buffers?}`.
- **`SplitState = (stripped_state, buffer_paths, buffers)`** — the shared intermediate
  that `remove_buffers` already returns. `build_comm_open`, `build_update`, and the new
  `dump_model` all produce this, then frame it differently; naming it lets them share the
  split + immutable-field injection instead of duplicating it. A single pure step
  `encode_buffers_base64: SplitState -> JsonSplitState` (and its inverse) is the *only*
  new buffer logic; the reconciler, if ever built, reuses it.
- **`Message = CommOpen | Update | Custom | Close`** — a sum type (frozen dataclass per
  variant). Today `build_comm_open`, `build_update`, `build_custom` return
  different-arity tuples/dicts discriminated by a string, so a list of "messages" has no
  common type and no exhaustiveness guarantee. Reconstruction *replays* messages, so this
  matters in the committed scope: make the `build_*` functions return a `Message`, have
  `Transport.send` accept one, and mypy can enforce exhaustive handling (`assert_never`).
  This is a small Tidy-First structural change to Layer 0 — see Open questions.

### Functions

Pure core functions over state dicts, mirroring the ipywidgets producer so bytes match:

- `dump_model(entry: ModelEntry) -> Record` — `remove_buffers(state)` →
  `encode_buffers_base64` → frame the `Record` (immutable anywidget fields injected as in
  `build_comm_open`).
- `load_model(record: Record) -> ModelEntry` — inverse: base64-decode → `put_buffers` →
  a live state dict ready to feed a `Widget`. (`put_buffers` mutates in place and returns
  `None`; `load_model` wraps it to return the state, restoring composability at the
  boundary.)
- `dump_document(entries: Iterable[ModelEntry]) -> Document` /
  `load_document(doc: Document) -> list[ModelEntry]` — `map` the pair over the
  model_id-keyed envelope. Same fixpoint type in and out, so `load_document ∘
  dump_document` is a checkable endomorphism on `list[ModelEntry]`.

`_esm`/`_css` are already part of state, so a saved `Document` is **self-contained**: it
reconstructs a fully renderable UI (including composed children, via `IPY_MODEL_` refs)
with its frontend code inline.

**model_id is the primary key — validate at the boundary.** `Widget.model_id` currently
defaults to `""` (`src/cositos/model.py`). Two default widgets would collide on the empty
key and silently lose state. Phase 1 **must reject** empty or duplicate `model_id`s when
building a `Document` (parse, don't validate). Loading is pure id-lookup, so a reference
graph with **cycles** (a widget referencing an ancestor — which ipywidgets permits) is
safe: refs are just strings resolved against the keyed map, no recursive reconstruction.

**Reconstruction API — decision needed (Option A recommended).**
- **A. Pure functions only** — host owns object reconstruction: `load_document` → host
  builds its state objects from the dicts → `Widget(...).open()` per model. Matches the
  current "core is pure, host owns state" seam exactly. Zero new layers. *Recommended.*
- **B. Stateful `WidgetStore`** that owns state and rehydrates `Widget`s directly. More
  ergonomic, but adds a state-owning layer the current design deliberately avoids
  (anti-complexity). Deferred; can be built on A later if wanted.

### Rich payloads: float arrays and DataFrames (awareness, not core)

Widgets are dominated by numeric arrays (numpy) and tabular data (pandas). These are
**not** JSON and **not** `bytes` — so where do they fit?

- **The core stays byte-oriented.** cositos already treats any `bytes`/`bytearray`/
  `memoryview` as a binary buffer. A numpy array reaches the protocol as a `memoryview`
  of its data, with `dtype`/`shape` carried as **plain state keys** next to it (the
  ipywidgets convention, e.g. `{"shape": (10,10), "dtype": "float32", "data":
  memoryview}`). So arrays already round-trip through serialization with zero core
  changes — the buffer holds the bytes, the envelope holds the shape/dtype.
- **Rich-type ↔ bytes conversion is a codec layer, per-language, optional — not core.**
  `numpy.ndarray ⇄ (bytes, dtype, shape)` and `DataFrame ⇄ Arrow IPC bytes` are inverse
  pairs registered per type (a small codec registry, i.e. a coproduct of codecs). Keeping
  them out of the core preserves the binding-free charter and keeps the round-trip law
  pure JSON+bytes. DataFrames specifically should serialize to **Arrow IPC bytes** (a
  single buffer) rather than split-JSON, since that is what the fast table frontends
  (perspective, datagrid) consume.
- **Byte-equality is mandatory for the round-trip law.** ipywidgets compares buffers with
  `memoryview(x).cast('B')` (`ipywidgets/.../widgets/widget.py:147-167`) because a
  `float32` memoryview compares unequal to a plain-bytes memoryview with identical bytes —
  the format/dtype info differs. The serialization round-trip test and PBT MUST compare
  buffers as raw bytes (`.cast('B')` / `tobytes()`), never by `memoryview` equality, or
  float-array fixtures will spuriously fail.

### Cross-language contract addition
- OpenSpec requirement **"Widget State Serialization Round-Trip"** + golden
  `fixtures/widget-state.json` (a small *composed* UI — a container with a child ref and
  one **float32 array buffer** carrying `shape`/`dtype`). This is the only new
  fixture-certified contract in the committed scope. Round-trip comparison is by raw
  bytes, per the byte-equality note above.

### Plan (committed)
1. **Type foundation (Tidy-First, structural).** Introduce `ModelEntry`, `Document`,
   `SplitState`, and the `Message` sum type; migrate `build_*`/`Transport.send` to
   `Message`. No behaviour change — its own commit(s).
2. **Serialization + composition (behaviour).** `dump/load_model`, `dump/load_document`,
   `encode/decode_buffers_base64`, non-empty/unique `model_id` validation,
   `widget-state.json` fixture (with a float32 array buffer), OpenSpec requirement,
   round-trip tests (byte-equality). *(Option A / inline ESM / base64.)* Composition rides
   the same code path — no extra work.

### Round-trip law (PBT)
- `load_document(dump_document(entries)) == entries` and
  `dump_document(load_document(doc)) == doc`, over generated `Document`s that include a
  binary buffer, a float-array buffer (`dtype`/`shape`), and an `IPY_MODEL_` child ref.
- `decode_buffers_base64 ∘ encode_buffers_base64 == id` on `SplitState`.
- Buffer comparison is **raw-byte** (`.cast('B')`). Use applicative generators
  (`prop_map`/tuples), not monadic — faster shrinking.

### Open questions (committed scope)
- **Reconstruction API:** confirm Option A (pure functions, host owns rebuild).
- **`Message` sum type in Phase 1?** It touches `Transport.send` and every `build_*`
  return type — a Tidy-First structural change slightly larger than "just serialization,"
  but it aligns builders, replay, and any future reconciler on one type. Confirm folding
  it in vs. a separate prior structural commit.
- **ESM:** inline-per-widget for v0 (self-contained, matches ipywidgets) — confirm, vs.
  dedupe shared ESM later.

---

## Explored, not committed (revisit only when a real need appears)

The user asked about "maybe an Elm architecture" and auto-generated UIs. These are
recorded here so the option space isn't lost, **but they are explicitly out of scope**
until Phase 1 ships and a concrete need is demonstrated. Building them now would violate
YAGNI.

**Important correction to the earlier framing:** "refresh only what changed without
rebuilding everything" is **already solved today**. `Widget.send_state(include={"value"})`
(`src/cositos/model.py`) sends only the changed key via `build_update`; existing widgets
stay alive across trait changes — that is how the protocol already works. A reconciler is
therefore **not** an independent requirement; it is only needed *if* one later adopts
whole-tree Elm re-rendering and must diff successive `Document`s. It is a consequence of
choosing Elm, not a prerequisite for cheap refresh.

- **Elm/TEA app layer** — `Model`, `Msg`, `update(msg, model) -> model`,
  `view(model) -> Document`; a `reconcile(prev, next) -> list[Message]` diff emitting standard
  protocol messages (trait `update` for changed keys, `comm_open`/`comm_close` for
  added/removed ids, a `children` `update` for re-parenting). Enabling idea: the
  serialized `Document` doubles as a virtual DOM. Attractive (deterministic, serializable
  Model, replay), but it is a whole runtime + a second fixture-locked contract; defer.
- **Auto-view** — `auto_view(obj) -> Document`, generalising `interaction.py`'s
  `widget_from_abbrev`/`widget_from_single_value` (int→IntSlider, bool→Checkbox, …) to
  dataclasses/Pydantic → a `VBox` of labelled field widgets. Optional per-language
  ergonomics, not core.

If pursued later, each would get its own design pass, its own OpenSpec change, and (for
the reconciler only) its own golden fixtures.
