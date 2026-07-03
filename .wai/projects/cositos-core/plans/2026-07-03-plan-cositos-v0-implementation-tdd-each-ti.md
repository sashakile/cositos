# Plan: `cositos` v0 implementation (TDD)

Each ticket = one red→green→refactor cycle. Structural (Tidy First) commits precede
behavioural ones. Verified against `ah` scenarios + `pretender` thresholds.

## Phase 0 — Repo scaffolding (repo maintenance, no behaviour)
- [ ] P0.1 Add `README.md`, `LICENSE` (MIT), `.gitignore`, `llm.txt` — satisfy `wai way`.
- [ ] P0.2 Python packaging: `pyproject.toml` (uv), `src/cositos/`, `tests/`, ruff+pytest.
- [ ] P0.3 `justfile` (fmt/lint/test), `.editorconfig`, `_typos.toml`.
- [ ] P0.4 `pretender.toml` thresholds; `ah init` + first spec skeleton.

## Phase 1 — Buffer split/merge (pure, PF archetype)
- [ ] P1.1 RED: test `remove_buffers` on flat dict with one `bytes` value → state minus
      key, `buffer_paths=[["k"]]`, `buffers=[b...]`.
- [ ] P1.2 GREEN: implement `remove_buffers` (dict + list + nested, v2 rules).
- [ ] P1.3 RED/GREEN: `put_buffers` inverse; property test `merge(split(x)) == x`.
- [ ] P1.4 Golden fixture: `fixtures/buffers_nested.json`.

## Phase 2 — Message builders (pure, PF)
- [ ] P2.1 RED: `build_comm_open(state)` emits the six immutable fields +
      `_model_module="anywidget"`, `_esm`, metadata `{"version":"2.1.0"}`.
- [ ] P2.2 GREEN: implement `protocol.build_comm_open`.
- [ ] P2.3 RED/GREEN: `build_update(state)` → `{method:"update",state,buffer_paths}`.
- [ ] P2.4 RED/GREEN: `parse_message` → Update | RequestState | Custom; unknown → error.
- [ ] P2.5 Golden fixtures: `comm_open.json`, `update.json`, `custom.json`.

## Phase 3 — Transport seam + Widget façade (SA archetype)
- [ ] P3.1 Define `Transport` protocol (send, on_message, supports_receive).
- [ ] P3.2 RED: with an in-memory FakeTransport, `Widget.open()` pushes one comm_open;
      `send_state()` pushes an update; inbound `request_state` triggers full update.
- [ ] P3.3 GREEN: implement `model.Widget` wiring core → transport.
- [ ] P3.4 RED/GREEN: inbound `update` calls state setter; buffers merged first.

## Phase 4 — Python host adapter (BP archetype)
- [ ] P4.1 `CommTransport` adapter over the `comm` package (create_comm / on_msg / send).
- [ ] P4.2 `_repr_mimebundle_` via `mimebundle()` (widget-view+json, model_id).
- [ ] P4.3 Integration test with a fake `comm` double (no live kernel): open→update→recv.

## Phase 5 — Conformance harness
- [ ] P5.1 `cositos.conformance`: load `fixtures/*.json`, assert builders reproduce them.
- [ ] P5.2 Document "how to certify a new-language port" in `docs/porting.md`.

## Quality gates (run each ticket)
- `pretender check src/` — complexity within thresholds.
- `ah check` — declared scenarios pass.
- `dont` — ground any non-obvious protocol claim against `messages.md` (needs external
  evidence support; see TOOL_EVALUATION.md finding on path-escape).

## Definition of done for v0
Core (buffers + protocol + model + transport seam) is fixture-certified, the Python
adapter round-trips against a fake comm, and `docs/porting.md` tells a Julia/C#/R author
exactly what to implement and how to self-verify.

