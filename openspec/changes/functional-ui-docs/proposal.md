## Why

An investigation of phronemophobic's "How to build a functional UI library from scratch" blog series (grounded against the implementation in `.wai/projects/investigations/research/2026-09-03-membrane-blog-series-functional-ui.md`) found that cositos already *practices* membrane's core principles — pure reducer returning effects, "parent is in charge", the Document as a UI intermediate representation — but never says so. The docs use "effect" for two different things (reducer commands vs. shell execution), cite only Redux/Elm as convergent prior art, and give widget authors no vocabulary or convention for intent-shaped `msg:custom` messages. This is a cheap, zero-risk docs improvement that strengthens the architecture story and the authoring guidance.

## What Changes

- `docs/extending/architecture.qmd`:
  - Add the **event → intent → effect** vocabulary (membrane's definitions) to "The lifecycle reducer" section, with membrane cited as the third convergent data point alongside Redux and Elm; clarify that cositos reducer effects are *transport commands* and that domain intents travel inside `custom` message content by convention.
  - Add a **UI-IR criteria checklist** (lossless, inspectable/translatable without the source runtime, independent of source and target formats) to "The Document is the virtual DOM" section, as an evaluation rubric for future Document-format changes.
- `docs/using/state-discipline.qmd`: add a one-sentence cross-reference noting the rules are the measured version of membrane's "parent is in charge" component principle.
- `docs/using/authoring-widgets.qmd` (and/or the dashboard tutorial): document a **recommended `msg:custom` content convention** extending the existing `{event, ...}` dict family used by `examples/widgets/` (e.g. `{"event": "set", "path": [...], "value": ...}`) so app-level intents stay reusable and host-side MVU `update(msg, state)` functions can apply them generically. Wire protocol unchanged — convention, not machinery.

## Capabilities

### New Capabilities
- `functional-ui-docs`: Documentation conventions — intent/effect vocabulary in the architecture page, the UI-IR criteria checklist, the "parent is in charge" cross-reference, and the intent-shaped `msg:custom` authoring convention.

### Modified Capabilities

(none — no spec-level behavior changes; docs only)

## Impact

- Docs only: `docs/extending/architecture.qmd`, `docs/using/state-discipline.qmd`, `docs/using/authoring-widgets.qmd` (and optionally `docs/using/dashboard.qmd`).
- No code, protocol, fixture, or test changes. No wire-format impact.
- Source of truth for content: `.wai/projects/investigations/research/2026-09-03-membrane-blog-series-functional-ui.md` (findings F1, F2, F3, F6; F4's private-state key convention is deliberately out of scope — gated by a separate external verification of stock-AnyModel arbitrary-key tolerance).
