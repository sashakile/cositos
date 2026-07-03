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

### Requirement: Inbound Message Parsing
The system SHALL parse inbound comm messages into typed events and reject unknown methods.

#### Scenario: Unknown method is rejected
- **GIVEN** an inbound comm message whose `method` is not update, request_state, or custom
- **WHEN** `parse_message` is called
- **THEN** it raises an error rather than silently ignoring the message
