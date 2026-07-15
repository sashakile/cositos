## Why

The core cost of porting cositos to a new kernel language is no longer the protocol
message builders (already small, fixture-certified, and consistent across five ports) —
it is the **widget lifecycle** (`open`/`send_state`/`close`, inbound dispatch, state
machine rules). Two of five ports (C#, R) stopped at the core, never building a live
widget, and the porting guide has no lifecycle step at all. The three that did build one
(Python, Julia, Clojure) each hand-rolled an imperative object with undocumented rules
(idempotency, identity re-merge on full send, comm-id adoption, one-way degrade) — and
Julia shipped a real bug (missing identity re-merge, since fixed) that a fixture-tested
reducer would have caught.

Extracting the lifecycle into a **pure, fixture-tested reducer** — the same shape the
protocol core already uses — makes the contract explicit, testable without a live kernel,
and uniform across languages, without adding a compiled core or runtime service.

## What Changes

- **Extract widget lifecycle into a pure `reduce` function** operating on `(phase, event, state) → (new_phase, effects[])`, parallel to how `build_comm_open` / `build_update` / `parse_message` are already pure functions.
- **Define an effect vocabulary** (`Send`, `Listen`, `ApplyState`, `InvokeCustom`) as plain data — never side-effecting — so the reducer is fixture-testable like the protocol core.
- **Implement an imperative shell** (~10-20 lines per language) that walks the effect list and delegates to the real `Transport` / host callbacks.
- **Generalize the one-way degrade flag** from `supports_receive` into per-event-kind capability flags (`supports_request_state`, `supports_custom`, `supports_buffers`), so Clojure's transport limitations are explicit rather than silently absent.
- **Document Clojure's permanent capability degrade** (no buffers, no `custom`, no `request_state`) as a known transport limitation, not a lifecycle bug.
- **No breaking changes** to the existing `Widget` API. The `Widget` class retains its public interface (`open`, `send_state`, `send_custom`, `close`, `mimebundle`, `_repr_mimebundle_`). Its internals are replaced by the shell in a single commit once both reducer and shell are fixture-certified and parity-tested against the existing test suite.
- **Migration path**: the old imperative `Widget` and the new reducer+shell coexist for one release cycle. Python tests certify both produce identical behavior. Once certified in Python and Julia, the old `Widget` internals are replaced by the shell — end-user code never changes.

## Capabilities

### New Capabilities

- `lifecycle`: Pure widget lifecycle reducer — a `reduce(phase, event, state) → (new_phase, effects[])` function that encodes the widget state machine (Unopened/Open/Closed), event vocabulary (Open, SendState, SendCustom, Inbound, Close, CommIdAssigned), and effect vocabulary (Send, Listen, ApplyState, InvokeCustom) as plain, fixture-testable data. Replaces the hand-written imperative Widget object with a composable, cross-language specification.
- `lifecycle-shell`: The imperative adapter layer that calls `reduce`, executes effects against a real Transport, and returns transport-generated data (comm id, capability flags) back as events. One implementation per language, trivially testable in isolation since the reducer carries all the logic.

### Modified Capabilities

- `protocol`: Add a requirement for cycle detection and depth capping in the buffer-split algorithm (`remove_buffers` / `_separate`), currently only implemented in Python. The spec currently has a "Binary Buffer Round-Trip" requirement but does not specify the behavior on cyclic or deeply nested state.
- `protocol`: Add fixture coverage for buffer-split edge cases (cycles, depth limit exceeded) — no existing fixture exercises these paths.

## Impact

- **Python**: Extract the lifecycle from `model.py` (the `Widget` class) into the pure `reduce` + shell pattern. The `Widget` class API is preserved as a thin shell until fixtures certify the reducer.
- **Julia**: Replace the lifecycle code in `Cositos.jl` (lines ~383-475) with the shell, then certify against the same lifecycle fixtures. The existing `ijulia_transport` / `CositosIJuliaExt` remains unchanged.
- **Clojure**: Document the permanent transport degrade. No lifecycle reducer for the `clojupyter_transport` path (it cannot express the full event vocabulary). The certified `core.clj` is unchanged.
- **C# / R**: Add a lifecycle shell and the reducer — these ports currently have no lifecycle at all, and this change is the first step toward a live widget in each.
- **Docs**: Update `docs/porting.md` to include a Step 5 (widget lifecycle), and update `docs/reference/api-cheatsheet.qmd` with the new `reduce` and effect vocabulary symbols.
- **Fixtures**: Add a `fixtures/lifecycle/` directory with golden files for `reduce` input/output tuples — one file per event type (open, full-send, filtered-send, inbound-update, inbound-request-state, inbound-custom, inbound-unknown, close, comm-id-assigned, one-way-open).
