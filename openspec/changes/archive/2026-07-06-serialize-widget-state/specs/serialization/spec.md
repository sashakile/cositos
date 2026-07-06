## ADDED Requirements

### Requirement: Widget State Round-Trips Through JSON
The system SHALL serialize widget state to, and reconstruct it from, the ipywidgets Widget
State JSON schema v2 (`application/vnd.jupyter.widget-state+json`), losslessly for all
JSON-compatible values and binary buffers.

#### Scenario: A single model round-trips losslessly
- **WHEN** a `ModelEntry` `(model_id, state)` is passed through `dump_model` and then `load_model`
- **THEN** the reconstructed `ModelEntry` equals the original, with binary buffers compared as raw bytes

#### Scenario: Binary buffers are base64-encoded per the v2 schema
- **WHEN** `dump_model` serializes a state containing a binary value
- **THEN** the buffer appears in the record's `buffers` array as `{path, encoding: "base64", data}` and not inside the JSON `state`

#### Scenario: The document envelope declares the state-format version
- **WHEN** `dump_document` produces a `Document`
- **THEN** the top level is `{version_major: 2, version_minor: 0, state: {…}}`, distinct from the protocol version `2.1.0`

### Requirement: Documents Preserve Composed Widget Graphs
The system SHALL preserve inter-widget references so a composed, nested UI reconstructs
intact from a single document.

#### Scenario: Child references survive a round-trip
- **GIVEN** a container model whose `state` holds `"IPY_MODEL_<child_id>"` reference strings and the referenced child models
- **WHEN** the models are passed through `dump_document` and then `load_document`
- **THEN** every reference string is preserved verbatim and every referenced `model_id` is present in the reconstructed document

#### Scenario: Reference cycles do not break loading
- **GIVEN** a document where two models reference each other by `model_id`
- **WHEN** `load_document` reconstructs it
- **THEN** loading completes without infinite recursion, because references are resolved by id lookup rather than by inlining

### Requirement: Model Identity Is Validated At The Boundary
The system SHALL require every serialized model to carry a non-empty, unique `model_id`,
since `model_id` is the document's primary key.

#### Scenario: Empty model_id is rejected
- **WHEN** `dump_document` is given a `ModelEntry` whose `model_id` is the empty string
- **THEN** it raises an error rather than emitting a model keyed by `""`

#### Scenario: Duplicate model_ids are rejected
- **WHEN** `dump_document` is given two `ModelEntry` values sharing the same `model_id`
- **THEN** it raises an error rather than silently overwriting one with the other

### Requirement: Serialized Documents Are Self-Contained
The system SHALL include each model's front-end code in its serialized state so a document
reconstructs a renderable UI without external assets.

#### Scenario: Front-end code is preserved
- **WHEN** a model whose `state` includes `_esm` (and optionally `_css`) is serialized and reconstructed
- **THEN** the reconstructed `state` contains the identical `_esm`/`_css` values
