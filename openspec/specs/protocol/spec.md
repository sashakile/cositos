# protocol Specification

## Purpose
Guarantee that cositos shapes and parses Jupyter widget messages exactly per the
ipywidgets protocol v2.1.0, so the anywidget frontend renders cositos widgets and any
language port can certify against the same behaviour.

## Requirements

### Requirement: Binary Buffer Round-Trip
The system SHALL split binary values out of widget state on send and merge them back on
receive, preserving structure per protocol v2 nested-buffer rules.

#### Scenario: Nested binary values are split and merged losslessly
- **GIVEN** a widget state containing binary values nested inside dicts and lists
- **WHEN** the state is passed through `remove_buffers` and then `put_buffers`
- **THEN** the reconstructed state equals the original state
- **AND** dict-keyed binaries are removed from state while list-indexed binaries become null

### Requirement: comm_open Carries Immutable anywidget Fields
The system SHALL include the immutable anywidget model/view fields and protocol version
metadata in every `comm_open` payload.

#### Scenario: comm_open includes AnyModel and AnyView identity
- **GIVEN** an arbitrary initial widget state
- **WHEN** `build_comm_open` is called
- **THEN** the state includes `_model_module="anywidget"`, `_model_name="AnyModel"`, and `_view_name="AnyView"`
- **AND** the metadata declares protocol version `2.1.0`

### Requirement: Full State Send Includes Immutable Identity Fields
When `send_state` performs a full state send (no `include` filter, equivalent to processing an inbound `request_state`), the resulting `update` message SHALL include the seven immutable anywidget identity fields in its state payload: `_model_module`, `_model_name`, `_model_module_version`, `_view_module`, `_view_name`, `_view_module_version`, and `_view_count`.

#### Scenario: Full send_state includes model identity
- **GIVEN** an open widget
- **WHEN** `send_state(w)` is called with no `include` argument
- **THEN** the resulting `update` message's `state` SHALL contain `_model_module` set to `"anywidget"`
- **AND** `_model_name` SHALL be set to `"AnyModel"`
- **AND** `_model_module_version` SHALL be set to the configured anywidget module version

#### Scenario: Full send_state includes view identity
- **GIVEN** an open widget
- **WHEN** `send_state(w)` is called with no `include` argument
- **THEN** the resulting `update` message's `state` SHALL contain `_view_module` set to `"anywidget"`
- **AND** `_view_name` SHALL be set to `"AnyView"`
- **AND** `_view_module_version` SHALL be set to the configured anywidget module version

#### Scenario: Explicit include skips identity merge
- **GIVEN** an open widget
- **WHEN** `send_state(w; include=["value"])` is called
- **THEN** the resulting `update` message's `state` SHALL contain only the `"value"` key
- **AND** SHALL NOT contain any of the immutable identity fields

#### Scenario: RequestState handler produces identity-bearing reply
- **GIVEN** an open widget with a listener for incoming messages
- **WHEN** the widget receives a `request_state` message
- **THEN** the handler SHALL send an `update` reply whose `state` includes all seven immutable identity fields

### Requirement: Inbound Message Parsing
The system SHALL parse inbound comm messages into typed events and ignore unknown methods (matching ipywidgets' forward-compatible dispatch).

#### Scenario: Unknown method is ignored
- **GIVEN** an inbound comm message whose `method` is not update, request_state, or custom (or is missing)
- **WHEN** `parse_message` is called
- **THEN** it returns a benign `Ignored` event rather than raising, so the caller no-ops on it
