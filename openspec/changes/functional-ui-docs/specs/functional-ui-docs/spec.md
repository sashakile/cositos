## ADDED Requirements

### Requirement: Architecture docs define the intent/effect vocabulary

The architecture documentation (`docs/extending/architecture.qmd`, "The lifecycle reducer" section) SHALL define the event → intent → effect vocabulary: an **event** is data representing a user action; an **intent** is data representing what the user wants done to application state; an **effect** is the carrying out of an intent; a reducer **effect** in cositos is a transport command executed by the shell. It SHALL cite membrane (phronemophobic) as a third convergent data point alongside Redux and Elm, and SHALL state that domain intents travel inside `custom` message content by convention.

#### Scenario: Reader can distinguish commands from intents

- **WHEN** a reader consults the architecture page's lifecycle-reducer section
- **THEN** they find definitions distinguishing transport-command effects (`Send`, `Listen`, `ApplyState`, `InvokeCustom`, `Error`) from domain intents carried in `custom` message content, with membrane cited as convergent prior art

### Requirement: Architecture docs provide UI-IR evaluation criteria

The architecture documentation ("The Document is the virtual DOM" section) SHALL present a checklist of intermediate-representation criteria for evaluating Document-format changes: lossless round-trip, inspectable/translatable without the source runtime, and independence from source and target formats.

#### Scenario: Evaluating a Document-format change

- **WHEN** a maintainer considers changing the Document format
- **THEN** the architecture page provides the IR criteria checklist to evaluate the change against

### Requirement: State-discipline docs reference the component principle

The state-discipline documentation (`docs/using/state-discipline.qmd`) SHALL include a cross-reference stating that its rules are the measured version of membrane's "parent is in charge" component principle (parents decide which child state is essential vs. incidental and retain the final word on child intents).

#### Scenario: Reader follows the lineage cross-reference

- **WHEN** a reader reads the state-discipline rules
- **THEN** the page links to the membrane principle it instantiates, marking the rules as measured evidence for the component-level claim

### Requirement: Authoring docs recommend an intent-shaped custom-message convention

The authoring documentation (`docs/using/authoring-widgets.qmd`) SHALL recommend a `msg:custom` content convention that extends the existing `{event, ...}` dict family used by `examples/widgets/` — e.g. `{"event": "set", "path": [...], "value": ...}` — such that host-side MVU `update(msg, state)` functions can apply intents generically. The convention SHALL be documented as host-side only, requiring no frontend or kernel machinery, and inert on stock anywidget. The wire protocol MUST NOT change.

#### Scenario: Widget author follows the convention

- **WHEN** a widget author needs the kernel to mutate a specific piece of domain state
- **THEN** the authoring docs show a `msg:custom` payload in the `{event, path, value}` dict family and an MVU `update(msg, state)` that applies it, consistent with `examples/widgets/` conventions

#### Scenario: Convention degrades on stock anywidget

- **WHEN** a widget following the convention runs on the published anywidget frontend
- **THEN** messages pass through unchanged (`msg:custom` is emitted verbatim) and no frontend or kernel machinery is required
