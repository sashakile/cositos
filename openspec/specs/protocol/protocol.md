---
id: protocol
kind: intent
statement: "WHEN cositos shapes or parses Jupyter widget comm messages THE system SHALL conform exactly to the ipywidgets protocol v2.1.0 nested-buffer and dispatch rules so the anywidget frontend renders cositos widgets and every language port certifies against the same behaviour"
---

# protocol

Guarantees that cositos shapes and parses Jupyter widget messages exactly per the
ipywidgets protocol v2.1.0: binary values are split out of widget state on send and
merged back on receive, comm_open and full state sends carry the immutable anywidget
identity, and inbound dispatch is forward-compatible with unknown methods. Any language
port certifies against the same behaviour.

## Constraints

| id | kind | expr | traces_to |
|----|------|------|-----------|
| c1 | invariant | remove_buffers followed by put_buffers reconstructs the original state exactly: dict-keyed binaries are removed from state, list-indexed binaries become null, and buffers are merged back losslessly per the protocol v2 nested-buffer rules | [[protocol]] |
| c2 | invariant | remove_buffers rejects a cyclic container by raising a ValueError naming the path, and rejects nesting beyond _MAX_DEPTH (500 levels) the same way — never unbounded recursion or a raw RecursionError | [[protocol]] |
| c3 | invariant | shared acyclic subtrees — the same container referenced by two different parent keys, a DAG — are not misidentified as cycles: remove_buffers succeeds | [[protocol]] |
| c4 | invariant | every comm_open payload carries the immutable anywidget identity (_model_module anywidget, _model_name AnyModel, _view_name AnyView) and metadata declaring protocol version 2.1.0 | [[protocol]] |
| c5 | invariant | a full state send — no include filter, equivalent to an inbound request_state reply — includes all seven immutable identity fields (_model_module, _model_name, _model_module_version, _view_module, _view_name, _view_module_version, _view_count); an explicit include filter yields exactly the included keys and no identity fields | [[protocol]] |
| c6 | invariant | an inbound comm message whose method is unknown or missing parses to a benign Ignored event rather than raising, so the caller no-ops on it | [[protocol]] |

## Model

### States

- `state`
- `split`

### Transitions

| id | from | to | guard |
|----|------|----|-------|
| t1 | state | split | [[protocol.c2]] |
| t2 | split | state | [[protocol.c1]] |
| t3 | state | state | [[protocol.c6]] |

## Properties

| id | kind | derives_from | generator | predicate |
|----|------|--------------|-----------|-----------|
| p1 | unit | [[protocol.c1]] | a widget state with binary values nested inside dicts and lists | remove_buffers then put_buffers equals the original state |
| p2 | unit | [[protocol.c2]] | a state containing a self-referential container, and a state nested beyond 500 levels | each raises a ValueError naming the path and never a RecursionError |
| p3 | unit | [[protocol.c3]] | a state where the same container is referenced by two different parent keys | remove_buffers succeeds without a cycle error |
| p4 | unit | [[protocol.c4]] | an arbitrary initial widget state | build_comm_open's state includes the anywidget identity fields and its metadata declares version 2.1.0 |
| p5 | unit | [[protocol.c5]] | an open widget sending state with include None, and with include set to value | the update state carries all seven identity fields, or exactly the included keys with none of them |
| p6 | unit | [[protocol.c5]] | an open widget receiving a request_state message | the update reply's state includes all seven immutable identity fields |
| p7 | unit | [[protocol.c6]] | an inbound message with an unknown or missing method | parse_message returns an Ignored event without raising |
