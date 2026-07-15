## Why

Julia's `send_state!` omits the anywidget identity re-merge on a full send (no `include` argument), unlike the Python reference implementation. When JupyterLab reloads without a kernel restart, it sends a `request_state` message to recover widgets — but the Julia reply lacks `_model_name`, `_model_module`, and the other identity fields anywidget's frontend needs to pick a view class. The widget never re-renders after the reload. Python fixed this same defect internally (`cositos-k43`); Julia has the same code path but never got the fix.

## What Changes

- **Julia `send_state!`**: On a full send (`include=nothing`), merge `model_identity` and `view_identity` into the state before building the update, mirroring Python's `Widget.send_state`
- **Julia host test**: Add a regression test asserting identity fields are present after a full `send_state!` (the exact shape of the `request_state` reconnection trigger)
- **Protocol spec**: Add a requirement that `update` messages from `send_state` carry the immutable anywidget identity fields when doing a full send — this is currently only documented/inspected for `comm_open`

## Capabilities

### New Capabilities

*(None — this is a bug fix that aligns Julia with existing Python behavior.)*

### Modified Capabilities

- `protocol`: ADD a requirement that `update` messages resulting from a full `send_state` (or a `request_state` handler) SHALL include the immutable anywidget identity fields (`_model_module`, `_model_name`, `_model_module_version`, `_view_module`, `_view_name`, `_view_module_version`, `_view_count`). This is the spec-level encoding of the `cositos-k43` fix that was previously only documented in Python source code.

## Impact

- `julia/src/Cositos.jl` — `send_state!` function (lines 431–440)
- `julia/test/host_tests.jl` — new regression test
- `openspec/specs/protocol/spec.md` — new requirement for update identity fields
- All language ports are implicitly affected at the spec level; only Julia gets an implementation change in this ticket
