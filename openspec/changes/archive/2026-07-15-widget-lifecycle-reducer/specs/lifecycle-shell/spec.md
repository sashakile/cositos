## ADDED Requirements

### Requirement: Imperative Shell Calls Reduce and Executes Effects
The system SHALL provide a thin imperative shell per language that (a) feeds user/host actions and transport events into `reduce`, (b) walks the returned effect list and calls the real `Transport`/host callbacks, and (c) handles the comm-id feedback loop synchronously after a `comm_open` send effect.

#### Scenario: Shell dispatches send effect to transport.send
- **GIVEN** a shell with a `Transport` and a phase of `"open"`
- **WHEN** `reduce` returns a `send` effect
- **THEN** the shell SHALL call `transport.send(msg_type, data, buffers=buffers, metadata=metadata)` with the exact parameters from the effect

#### Scenario: Shell dispatches listen effect to transport.on_message
- **GIVEN** a shell with a `Transport` that has `supports_receive=True`
- **WHEN** `reduce` returns a `listen` effect
- **THEN** the shell SHALL call `transport.on_message(callback)` where `callback` feeds subsequent inbound data back as `inbound` events to `reduce`

#### Scenario: Shell dispatches apply_state effect to host set_state
- **GIVEN** a shell with a host `set_state` callback
- **WHEN** `reduce` returns an `apply_state` effect
- **THEN** the shell SHALL call the host's `set_state(state)` with the effect's state dict

#### Scenario: Shell dispatches invoke_custom effect to host on_custom
- **GIVEN** a shell with a host `on_custom` callback
- **WHEN** `reduce` returns an `invoke_custom` effect
- **THEN** the shell SHALL call the host's `on_custom(content, buffers)` with the effect's content and buffers

#### Scenario: Shell handles comm-id feedback loop
- **GIVEN** a shell that has just executed a `send` effect with `msg_type="comm_open"`
- **WHEN** the shell reads `transport.comm_id()` and finds a non-empty string
- **THEN** the shell SHALL feed a `comm_id_assigned` event back into `reduce`
- **AND** execute any resulting effects (typically zero)

### Requirement: Capability Flags Are Passed to Reduce
The shell SHALL query the transport's capability flags once and pass them as a `TransportCapabilities` struct to every `reduce` call. The reducer uses these flags to decide which effects to produce — the shell never blocks or rewrites events based on capabilities.

#### Scenario: One-way transport capabilities suppress listen effect in the reducer
- **GIVEN** a transport with `supports_receive=False`
- **WHEN** the shell calls `reduce(phase, open_event, current_state, capabilities)` with those capabilities
- **THEN** the returned effects SHALL NOT contain a `listen` effect (the reducer omits it based on capabilities — the shell does NOT filter after the call)

#### Scenario: Transport without buffers suppresses buffer-carrying sends in the reducer
- **GIVEN** a transport with `supports_buffers=False`
- **WHEN** the shell calls `reduce` with any event
- **THEN** any returned `send` effects SHALL carry an empty buffers list (the reducer respects the capabilities — the shell does NOT sanitize after the call)

#### Scenario: Transport without custom returns error effect on send_custom
- **GIVEN** a transport with `supports_custom=False`
- **WHEN** the shell calls `reduce(phase, send_custom_event, current_state, capabilities)` with those capabilities
- **THEN** the returned effects SHALL contain an `error` effect indicating custom messages are not supported by this transport

### Requirement: Shell Preserves Existing Public API
The shell SHALL expose the same public API as the existing `Widget` class (`open`, `send_state`, `send_custom`, `close`, `mimebundle`, `_repr_mimebundle_`) so existing end-user code continues to work without changes.

#### Scenario: Public API signatures are unchanged
- **WHEN** the shell replaces the old `Widget` implementation
- **THEN** every public method SHALL accept the same parameters and return the same types as the existing `Widget` class

#### Scenario: _repr_mimebundle_ auto-opens before returning bundle
- **GIVEN** a shell in phase `"unopened"`
- **WHEN** `_repr_mimebundle_()` is called (as happens when a bare `widget` is the last expression in a Jupyter cell)
- **THEN** the shell SHALL call `reduce` with an `open` event before producing the mimebundle
- **AND** the returned bundle SHALL reference the widget's (possibly comm-id-adopted) `model_id`