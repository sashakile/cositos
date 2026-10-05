---
id: lifecycle
kind: intent
statement: "WHEN reduce is called with any (phase, event, current_state, capabilities) quadruple THE system SHALL return a deterministic (new_phase, effects) pair that encodes the widget lifecycle state machine without I/O or side effects"
---

# lifecycle

Defines the pure widget lifecycle reducer every cositos backend implements: widget
open/send/close/inbound transitions are deterministic, cross-language, and
fixture-testable. The reducer operates on plain data — no transport, no host, no I/O —
so the same fixtures certify Python, Julia, R, C# and Clojure byte-for-byte.

## Constraints

| id | kind | expr | traces_to |
|----|------|------|-----------|
| c1 | invariant | reduce is pure: the same (phase, event, current_state, capabilities) quadruple always yields an identical (new_phase, effects) pair, with no I/O or side effects | [[lifecycle]] |
| c2 | invariant | from unopened, an open event yields phase open plus a send effect with msg_type comm_open, and a listen effect iff capabilities.supports_receive; a further open event in phase open is a no-op — phase unchanged, no effects | [[lifecycle]] |
| c3 | invariant | send_state and send_custom are honored only in phase open — send_state yields a send effect carrying an update, send_custom yields a send effect with msg_type comm_msg and the custom payload; from any other phase they yield an error effect and no send | [[lifecycle]] |
| c4 | invariant | a send effect carrying an update in phase open includes the seven immutable anywidget identity fields when include is None, and exactly the included keys when include is a set | [[lifecycle]] |
| c5 | invariant | close is honored only from open — open yields phase closed plus a send effect with msg_type comm_close; from unopened or closed it is a no-op: phase unchanged, no effects | [[lifecycle]] |
| c6 | invariant | inbound events in phase unopened or closed produce no effects and leave the phase unchanged; in phase open they dispatch by method — update to apply_state, request_state to send comm_msg, custom to invoke_custom | [[lifecycle]] |
| c7 | invariant | a comm_id_assigned event stores the assigned id, and it is reflected as the model_id field of subsequent mimebundle output | [[lifecycle]] |

## Model

### States

- `unopened`
- `open`
- `closed`

### Transitions

| id | from | to | guard |
|----|------|----|-------|
| t1 | unopened | open | [[lifecycle.c2]] |
| t2 | open | open | [[lifecycle.c4]] |
| t3 | open | closed | [[lifecycle.c5]] |
| t4 | unopened | unopened | [[lifecycle.c6]] |
| t5 | closed | closed | [[lifecycle.c6]] |

## Properties

| id | kind | derives_from | generator | predicate |
|----|------|--------------|-----------|-----------|
| p1 | unit | [[lifecycle.c1]] | an arbitrary (phase, event, current_state, capabilities) quadruple | two calls to reduce return identical (new_phase, effects) pairs |
| p2 | unit | [[lifecycle.c2]] | an unopened phase, an open event, and capabilities with an arbitrary supports_receive flag | the new phase is open, a send effect with msg_type comm_open is present, and a listen effect is present iff supports_receive; a second open event from the open phase leaves phase and effects unchanged |
| p3 | unit | [[lifecycle.c3]] | an unopened phase and a send_state or send_custom event | the effects contain an error effect and no send effect |
| p9 | unit | [[lifecycle.c3]] | an open phase and a send_custom event with an arbitrary payload | the effects contain a send effect with msg_type comm_msg carrying the custom payload |
| p4 | unit | [[lifecycle.c4]] | an open phase and a send_state event with include either None or an arbitrary key set | the send effect's data contains exactly the seven identity fields plus state, or only the included keys |
| p5 | unit | [[lifecycle.c5]] | an arbitrary phase and a close event | from open: phase closed and a send effect with msg_type comm_close; otherwise: phase unchanged and no effects |
| p6 | unit | [[lifecycle.c6]] | an inbound event with an arbitrary method, in phase unopened or closed | the phase is unchanged and no effects are produced |
| p7 | unit | [[lifecycle.c6]] | an inbound event in phase open with method update, request_state or custom | the effects contain apply_state, a send with msg_type comm_msg, or invoke_custom respectively |
| p8 | unit | [[lifecycle.c7]] | an open phase and a comm_id_assigned event with an arbitrary id string | the mimebundle model_id equals the assigned id |
