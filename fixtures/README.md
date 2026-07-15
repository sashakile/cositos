# Shared golden fixtures

This directory contains the JSON fixtures every cositos backend certifies against.
Each fixture file encodes a single scenario (message, state, or lifecycle transition)
as a JSON value that all five ports (Python, Julia, Clojure, C#, R) reproduce
byte-for-byte.

## Protocol fixtures

| File | What it certifies |
|---|---|
| `comm_open.json` | `build_comm_open(...)` — the anywidget-enriched comm_open message (identity fields, buffer split) |
| `update.json` | `build_update(...)` — a simple state update without buffers |
| `update_nested_buffer.json` | `build_update(...)` — a state update with a nested binary buffer (the one ports most often get wrong) |
| `custom.json` | `build_custom(...)` — a custom message payload |
| `widget-state.json` | `dump_document(...)` — the full serialization round-trip against the Widget State JSON schema v2 |

## Controls catalog

`controls-catalog.json` is the shared catalog of real `@jupyter-widgets/controls` widget
identities (model_module, model_name, model_module_version for IntSlider, Dropdown, VBox,
HBox, etc.). Used by the Julia controls extension (`CositosControlsExt`) to build
truly-identical frontend widgets without re-deriving the ipywidgets identity. Not
certified by the other backends.

| File | What it certifies |
|---|---|
| `comm_open.json` | `build_comm_open(...)` — the anywidget-enriched comm_open message (identity fields, buffer split) |
| `update.json` | `build_update(...)` — a simple state update without buffers |
| `update_nested_buffer.json` | `build_update(...)` — a state update with a nested binary buffer (the one ports most often get wrong) |
| `custom.json` | `build_custom(...)` — a custom message payload |
| `widget-state.json` | `dump_document(...)` — the full serialization round-trip against the Widget State JSON schema v2 |

## Lifecycle fixtures

The `lifecycle/` directory contains fixtures for the widget lifecycle reducer
(`reduce(phase, event, state, capabilities) → (new_phase, effects)`). Each file is a JSON
array of tuples representing one scenario:

```json
[phase_in, event, state_in, phase_out, effects, optional_capabilities]
```

- **`phase_in`** / **`phase_out`**: one of `"unopened"`, `"open"`, `"closed"`.
- **`event`**: an object with `"kind"` field, plus any event-specific fields.
- **`state_in`**: the current host widget state dict.
- **`effects`**: a list of effect objects, each with a `"kind"` field (`"send"`,
  `"listen"`, `"apply_state"`, `"invoke_custom"`, `"error"`). `"send"` effects also carry
  `"msg_type"` (`"comm_open"`, `"comm_msg"`, `"comm_close"`).
- **`optional_capabilities`** (6th element): overrides for `TransportCapabilities` fields
  (e.g. `{"supports_receive": false}`). Defaults to full capability when absent.

### Fixture files and what they cover

| File | Event kind | Scenarios |
|---|---|---|
| `open.json` | `open` | Unopened → open with `send` + `listen` effects |
| `one-way-open.json` | `open` | Unopened → open without `listen` (capabilities: `supports_receive=false`) |
| `full-send.json` | `send_state` | Open → full send with identity re-merge |
| `filtered-send.json` | `send_state` | Open → filtered send (only `include`d keys) |
| `inbound-update.json` | `inbound` | Inbound `update` produces `apply_state` effect |
| `inbound-request-state.json` | `inbound` | Inbound `request_state` produces full `send` effect |
| `inbound-custom.json` | `inbound` | Inbound `custom` produces `invoke_custom` effect |
| `inbound-unknown.json` | `inbound` | Inbound unknown method is silently dropped |
| `close.json` | `close` | Open → closed with `send(comm_close)` effect |
| `comm-id-assigned.json` | `comm_id_assigned` | No effects; shell stores the id |

### How to certify

In each backend's test runner, load every fixture file, construct the event and
capabilities from the JSON, call `reduce`, and assert:

1. The returned phase matches `phase_out`.
2. The returned effects have the same count and kinds as the fixture's effects list.

See the Python test (`tests/test_lifecycle.py`), Julia test (`julia/test/runtests.jl`),
C# test (`csharp/Program.cs`), and R test (`r/test.R`) for reference implementations.