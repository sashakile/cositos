# Tasks: serialize-widget-state

## 1. Named types (Tidy-First, structural — no behaviour)

- [ ] 1.1 Add `ModelEntry` (`(model_id: str, state: dict)`) and `Document` type aliases in `src/cositos/serialize.py`.
- [ ] 1.2 Add pure `encode_buffers_base64(split) -> json_split` and `decode_buffers_base64(json_split) -> split` over the `remove_buffers` triple `(stripped, buffer_paths, buffers)`; unit-test `decode ∘ encode == id` on a `SplitState` (raw-byte comparison).

## 2. Single-model serialization (behaviour, TDD)

- [ ] 2.1 RED: round-trip test — `load_model(dump_model(entry)) == entry` for a state with plain values and a binary buffer (compare buffers via `memoryview(...).cast('B')`).
- [ ] 2.2 GREEN: implement `dump_model` (inject immutable anywidget fields → `remove_buffers` → `encode_buffers_base64` → `{model_name, model_module, model_module_version, state, buffers?}`).
- [ ] 2.3 GREEN: implement `load_model` (decode base64 → `put_buffers` → return `ModelEntry`; wrap the in-place `put_buffers` so `load_model` returns state).
- [ ] 2.4 Test: `buffers` key omitted when the state has no binary values (matches ipywidgets).

## 3. Document serialization + composition (behaviour, TDD)

- [ ] 3.1 RED: round-trip test — `load_document(dump_document(entries)) == entries` and `dump_document(load_document(doc)) == doc` for a composed UI (container with an `"IPY_MODEL_<id>"` child ref + the child).
- [ ] 3.2 GREEN: implement `dump_document` (map `dump_model`; wrap in `{version_major:2, version_minor:0, state:{id: record}}`).
- [ ] 3.3 GREEN: implement `load_document` (unwrap envelope; map `load_model`).
- [ ] 3.4 Test: a reference cycle (two models referencing each other) loads without recursion.

## 4. model_id validation (boundary)

- [ ] 4.1 RED: `dump_document` raises on an empty `model_id` and on duplicate `model_id`s.
- [ ] 4.2 GREEN: validate non-empty + unique keys when assembling the document.

## 5. Cross-language contract fixture

- [ ] 5.1 Add `fixtures/widget-state.json`: a composed UI (container + child ref) whose child carries a **float32 array buffer** plus `shape`/`dtype` state keys.
- [ ] 5.2 Test: `dump_document` reproduces the fixture (buffers by raw bytes), and `load_document(fixture)` reconstructs the entries — the shared golden contract.

## 6. Wiring, PBT, docs

- [ ] 6.1 Re-export `dump_model`/`load_model`/`dump_document`/`load_document` from `src/cositos/__init__.py`.
- [ ] 6.2 Property-based round-trip test over generated documents (binary buffer + float-array buffer + `IPY_MODEL_` ref); applicative generators; raw-byte buffer comparison.
- [ ] 6.3 Add a serialization round-trip certification note to `docs/porting.md`.
- [ ] 6.4 `mise run verify` green (lint, typecheck, coverage, complexity, `openspec validate`).
