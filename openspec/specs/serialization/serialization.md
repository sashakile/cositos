---
id: serialization
kind: intent
statement: "WHEN widget state is serialized to or reconstructed from the ipywidgets Widget State JSON schema v2 THE system SHALL round-trip it losslessly, including binary buffers, inter-widget references and front-end code, validating model identity at the boundary"
---

# serialization

Defines how cositos serializes widget state to, and reconstructs it from, the ipywidgets
Widget State JSON schema v2 (`application/vnd.jupyter.widget-state+json`) — losslessly,
including binary buffers and inter-widget references — so a whole UI can be saved to
plain JSON and rebuilt later, and so every language port certifies against the same
contract.

## Constraints

| id | kind | expr | traces_to |
|----|------|------|-----------|
| c1 | invariant | a ModelEntry passed through dump_model and load_model reconstructs identically, with binary buffers compared as raw bytes | [[serialization]] |
| c2 | invariant | a binary value is serialized into the record's buffers array as {path, encoding base64, data} and never inside the JSON state | [[serialization]] |
| c3 | invariant | dump_document's envelope is {version_major 2, version_minor 0, state} — the state-format version, distinct from the protocol version 2.1.0 | [[serialization]] |
| c4 | invariant | every IPY_MODEL_ reference string survives a dump/load round-trip verbatim, and every referenced model_id is present in the reconstructed document; reference cycles load without infinite recursion because references resolve by id lookup, never by inlining | [[serialization]] |
| c5 | invariant | dump_document rejects a model_id that is empty or duplicated across entries, rather than emitting a model keyed by the empty string or silently overwriting a duplicate | [[serialization]] |
| c6 | invariant | a model's front-end code — _esm and, when present, _css — is contained in the serialized state and reconstructed identically | [[serialization]] |

## Model

### States

- `entry`
- `document`

### Transitions

| id | from | to | guard |
|----|------|----|-------|
| t1 | entry | document | [[serialization.c5]] |
| t2 | document | entry | [[serialization.c4]] |

## Properties

| id | kind | derives_from | generator | predicate |
|----|------|--------------|-----------|-----------|
| p1 | unit | [[serialization.c1]] | a ModelEntry whose state contains plain values and a binary buffer | dump_model then load_model equals the original entry, buffers compared as raw bytes |
| p2 | unit | [[serialization.c2]] | a state containing a binary value | the serialized record's buffers array holds {path, encoding base64, data} and the JSON state does not contain the bytes |
| p3 | unit | [[serialization.c3]] | a document of arbitrary models | the envelope is {version_major 2, version_minor 0, state} |
| p4 | unit | [[serialization.c4]] | a container model holding IPY_MODEL_ references plus the referenced child models | all reference strings are verbatim and every referenced model_id is present after load |
| p5 | unit | [[serialization.c4]] | a document where two models reference each other | load_document completes without infinite recursion |
| p6 | unit | [[serialization.c5]] | an entry with an empty model_id, and two entries sharing one model_id | dump_document raises in each case |
| p7 | unit | [[serialization.c6]] | a model whose state includes _esm and _css | the reconstructed state contains the identical _esm and _css values |
