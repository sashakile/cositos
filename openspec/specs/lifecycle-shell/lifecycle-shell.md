---
id: lifecycle.shell
kind: intent
statement: "WHEN the shell is driven by user/host actions or transport events THE system SHALL forward them to reduce with the transport's capability flags, execute every returned effect in order against the real transport and host callbacks, and preserve the existing public Widget API"
---

# lifecycle.shell

The thin imperative shell that calls the lifecycle reducer and executes the returned
effects, bridging between the pure reducer and the real transport/kernel APIs. The shell
never blocks or rewrites events itself — capability-based suppression lives entirely in
the reducer, and the shell's visible machine is exactly the reducer's phase machine.

## Constraints

| id | kind | expr | traces_to |
|----|------|------|-----------|
| c1 | invariant | the shell queries the transport's capability flags once and passes them as a TransportCapabilities struct to every reduce call | [[lifecycle.shell]] |
| c2 | invariant | the shell executes each returned effect exactly once, in order, with the exact parameters from the effect: send to transport.send(msg_type, data, buffers, metadata), listen to transport.on_message with a callback feeding inbound data back into reduce, apply_state to the host's set_state(state), invoke_custom to the host's on_custom(content, buffers) | [[lifecycle.shell]] |
| c3 | invariant | after executing a send effect with msg_type comm_open, the shell synchronously reads transport.comm_id() and, when it is a non-empty string, feeds a comm_id_assigned event back into reduce and executes any resulting effects | [[lifecycle.shell]] |
| c4 | invariant | with capabilities.supports_buffers false, no send effect carries a non-empty buffers list: the reducer suppresses buffer-carrying sends by yielding an error effect instead | [[lifecycle.shell]] |
| c5 | invariant | the shell exposes the same public API as the existing Widget class — open, send_state, send_custom, close, mimebundle, _repr_mimebundle_ — accepting the same parameters and returning the same types | [[lifecycle.shell]] |
| c6 | invariant | _repr_mimebundle_ called in phase unopened feeds an open event to reduce before producing the mimebundle, and the returned bundle references the widget's model_id | [[lifecycle.shell]] |

## Model

### States

- `unopened`
- `open`
- `closed`

### Transitions

| id | from | to | guard |
|----|------|----|-------|
| t1 | unopened | open | [[lifecycle.shell.c2]] |
| t2 | open | open | [[lifecycle.shell.c2]] |
| t3 | open | closed | [[lifecycle.shell.c2]] |
| t4 | unopened | unopened | [[lifecycle.shell.c1]] |
| t5 | closed | closed | [[lifecycle.shell.c1]] |

## Properties

| id | kind | derives_from | generator | predicate |
|----|------|--------------|-----------|-----------|
| p1 | unit | [[lifecycle.shell.c1]] | an arbitrary event in an arbitrary phase | the same TransportCapabilities struct derived from the transport is passed to every reduce call |
| p2 | unit | [[lifecycle.shell.c2]] | an arbitrary effect list over send, listen, apply_state and invoke_custom | each effect is dispatched exactly once, in order, with the exact parameters from the effect |
| p3 | unit | [[lifecycle.shell.c3]] | a shell that has just executed a comm_open send and a transport with a non-empty comm_id | a comm_id_assigned event is fed back into reduce and any resulting effects are executed |
| p4 | unit | [[lifecycle.shell.c4]] | capabilities with supports_buffers false and a buffer-carrying send_custom event | no send effect is produced carrying a non-empty buffers list |
| p5 | unit | [[lifecycle.shell.c5]] | each of the six public method names | the method's parameter list matches the existing Widget class reference |
| p6 | unit | [[lifecycle.shell.c6]] | a shell in phase unopened and a _repr_mimebundle_ call | an open event is fed to reduce before the bundle is produced, and the bundle references the widget's model_id |
