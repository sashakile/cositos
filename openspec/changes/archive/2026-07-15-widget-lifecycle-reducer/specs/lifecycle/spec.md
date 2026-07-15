## ADDED Requirements

### Requirement: Lifecycle Reducer Encodes Widget State Machine
The system SHALL provide a pure `reduce(phase, event, current_state, capabilities) → (new_phase, effects[])` function that encodes the widget lifecycle as a deterministic state machine, operating on plain data with no I/O or side effects.

`current_state` is the host widget state dict, fetched by the shell via `get_state()` and passed to `reduce` so the reducer can build message payloads without calling any closure. `capabilities` is a `TransportCapabilities` struct declaring which event kinds the transport can carry — the reducer uses these to decide which effects to produce.

#### Scenario: reduce is a pure function
- **GIVEN** the same `(phase, event, current_state, capabilities)` quadruple
- **WHEN** `reduce` is called twice
- **THEN** both calls return identical `(new_phase, effects)` pairs

#### Scenario: Unopened → open produces comm_open effect
- **GIVEN** a phase of `"unopened"`, an `open` event, a widget state dict, and a `TransportCapabilities` struct
- **WHEN** `reduce` is called
- **THEN** the new phase SHALL be `"open"`
- **AND** the effects SHALL contain a `send` effect with `msg_type="comm_open"` (carrying enriched state including identity fields)
- **AND** if `capabilities.supports_receive` is true, the effects SHALL contain a `listen` effect
- **AND** if `capabilities.supports_receive` is false, the effects SHALL NOT contain a `listen` effect

#### Scenario: Open → open (idempotent) is a no-op
- **GIVEN** a phase of `"open"` and an `open` event
- **WHEN** `reduce` is called
- **THEN** the new phase SHALL remain `"open"`
- **AND** the effects list SHALL be empty (no duplicate `comm_open`)

### Requirement: Send-state Produces Update Effect
The system SHALL translate a `send_state` event with optional `include` filter into a `send` effect carrying an `update` comm_msg.

#### Scenario: Full send_state includes identity fields
- **GIVEN** a phase of `"open"`, a `send_state` event with `include=None`, and a `current_state` dict containing `{"_esm": "...", "value": 0}`
- **WHEN** `reduce` is called
- **THEN** the effects SHALL contain a `send` effect whose `data` includes the seven immutable anywidget identity fields (`_model_module`, `_model_name`, `_model_module_version`, `_view_module`, `_view_name`, `_view_module_version`, `_view_count`) merged with the host state values from `current_state`

#### Scenario: Filtered send_state omits identity fields
- **GIVEN** a phase of `"open"`, a `send_state` event with `include=["value"]`, and a `current_state` dict containing `{"value": 5, "other": 1}`
- **WHEN** `reduce` is called
- **THEN** the effects SHALL contain a `send` effect whose `data` SHALL contain only the key `"value"` with its value `5`
- **AND** SHALL NOT include any identity fields or keys outside `include`

#### Scenario: Unopened send_state produces error effect
- **GIVEN** a phase of `"unopened"` and a `send_state` event
- **WHEN** `reduce` is called
- **THEN** the effects SHALL contain an `error` effect (kind `"error"`) containing a message indicating the comm is not open

### Requirement: Send-custom Produces Custom Effect
The system SHALL translate a `send_custom` event into a `send` effect carrying a custom comm_msg.

#### Scenario: Send_custom from open state
- **GIVEN** a phase of `"open"` and a `send_custom` event with content and optional buffers
- **WHEN** `reduce` is called
- **THEN** the effects SHALL contain a `send` effect with `msg_type="comm_msg"` and the custom payload

### Requirement: Inbound Messages Dispatch to Effects
The system SHALL translate inbound parsed messages into the appropriate effects: `ApplyState` for `update`, a `send` for `request_state`, and `InvokeCustom` for `custom`.

#### Scenario: Inbound update produces apply_state effect
- **GIVEN** a phase of `"open"` and an `inbound` event containing an `update` message whose state has already been buffer-merged by the shell (the shell calls `put_buffers` before feeding the event to `reduce`)
- **WHEN** `reduce` is called
- **THEN** the effects SHALL contain an `apply_state` effect carrying the pre-merged state dict
- **AND** the reducer SHALL NOT itself call `put_buffers` — buffer merge is the shell's responsibility

#### Scenario: Inbound request_state produces full send effect
- **GIVEN** a phase of `"open"` and an `inbound` event containing a `request_state` message
- **WHEN** `reduce` is called
- **THEN** the effects SHALL contain a `send` effect with `msg_type="comm_msg"` carrying an `update` that includes identity fields (same as full send_state)

#### Scenario: Inbound custom produces invoke_custom effect
- **GIVEN** a phase of `"open"` and an `inbound` event containing a `custom` message with content and buffers
- **WHEN** `reduce` is called
- **THEN** the effects SHALL contain an `invoke_custom` effect with the custom content and buffers

### Requirement: Inbound Message Delivery Is Phase-Safe
The reducer SHALL accept `inbound` events from any phase. Inbound messages arriving before the comm is opened or after it is closed SHALL NOT produce effects or change phase.

#### Scenario: Inbound from unopened is buffered for later delivery
- **GIVEN** a phase of `"unopened"` and an `inbound` event carrying an `update` message
- **WHEN** `reduce` is called
- **THEN** the phase SHALL remain `"unopened"`
- **AND** no effects SHALL be produced
- **AND** the inbound message SHOULD be stored for replay after a subsequent `open` event (the shell may instead queue at the transport level via `_pending`, matching how `CommTransport` handles callbacks registered before open)

#### Scenario: Inbound from closed is silently dropped
- **GIVEN** a phase of `"closed"` and any `inbound` event
- **WHEN** `reduce` is called
- **THEN** the phase SHALL remain `"closed"`
- **AND** the effects list SHALL be empty

### Requirement: Close Produces Comm-Close Effect
The system SHALL translate a `close` event into a `send` effect carrying a `comm_close`.

#### Scenario: Close from open state
- **GIVEN** a phase of `"open"` and a `close` event
- **WHEN** `reduce` is called
- **THEN** the new phase SHALL be `"closed"`
- **AND** the effects SHALL contain a `send` effect with `msg_type="comm_close"`

#### Scenario: Close from unopened or closed state is a no-op
- **GIVEN** a phase of `"unopened"` or `"closed"` and a `close` event
- **WHEN** `reduce` is called
- **THEN** the phase SHALL remain unchanged
- **AND** the effects list SHALL be empty

### Requirement: Comm-Id-Assigned Event Adopts Transport Id
The system SHALL accept a `comm_id_assigned` event and use the assigned id for subsequent mimebundle calls.

#### Scenario: Comm id is reflected in model_id after assignment
- **GIVEN** a phase of `"open"` and a `comm_id_assigned` event with id `"abc-123"`
- **WHEN** `reduce` is called
- **THEN** the shell SHALL store `"abc-123"` as the widget's `model_id`
- **AND** a subsequent `mimebundle()` call SHALL return a bundle whose `model_id` field is `"abc-123"`