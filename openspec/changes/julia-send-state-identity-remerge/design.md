## Context

Julia's `send_state!` (Cositos.jl lines 431–440) dispatches to `build_update(state)` without ever calling `model_identity`/`view_identity` — the two helpers that produce the seven immutable anywidget frontend fields. The `RequestState` handler in `_handle!` calls `send_state!(w)` with no `include` argument, which is exactly the JupyterLab-reload recovery path. Python's `Widget.send_state` handles this by merging identity fields when `include is None`.

Both `model_identity` and `view_identity` exist in `Cositos.jl` and are used elsewhere (e.g., `dump_model`), so no new protocol-level helpers are needed — only a call site change.

## Goals / Non-Goals

**Goals:**
- Make Julia's `send_state!` match Python's behaviour on a full send (no `include`)
- Ensure the `RequestState` handler produces a reply with identity fields
- Add a regression test that would catch a regression in any future refactor
- Document the requirement in the protocol spec so future language ports don't miss it

**Non-Goals:**
- No changes to Python, Clojure, C#, or R ports
- No changes to the `include`-filtering branch (that code path is correct)
- No changes to buffer split/merge or any other protocol message type
- No live-kernel JupyterLab integration test (unit test against the fake transport is sufficient for regression coverage)

## Decisions

1. **Use `merge` with exact keyword-arguments order mirroring Python's `**state` pattern.**
   Python does `{**model_identity, **view_identity, **state}` — identity fields come first so that real widget state cannot accidentally shadow them (identity fields are immutable anyway, but the ordering clarifies intent). Julia's `merge(model_identity(...), view_identity(...), state)` achieves the same: later dicts win in Julia's `merge`, so `state` keys override identity keys if there were a collision (there never should be, but this preserves the exact same semantics).

2. **No helper refactoring.**
   `model_identity` and `view_identity` already exist. Creating a combined `_immutable_fields` wrapper exists but is not exported/public. Either is fine; the clearest fix is to call them individually in `send_state!` to mirror Python's two explicit `**`-splats, with an inline comment referencing `cositos-k43`.

3. **Test uses the existing fake transport infrastructure.**
   The Julia test suite already has `make_widget`, `open!`, and a recording `FakeTransport`. The new test follows the same pattern as `"open! sends comm_open with protocol metadata + model identity"` but targets `send_state!` output instead.

## Risks / Trade-offs

- **[Low] `merge` key collision**: If widget state somehow contains a key like `_model_name`, Julia's `merge` would let it shadow the identity value. This is identical to Python's `**state` behaviour and is accepted by design — identity fields are never supposed to be part of user state.
- **[Low] Test parity gap**: The unit test uses a fake transport and cannot verify the full JupyterLab recovery path end-to-end. This is acceptable: the Python fix was validated the same way (unit test + reasoning), and live-browser testing is impractical in CI.
