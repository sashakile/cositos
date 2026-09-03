## 1. Architecture page — vocabulary and IR criteria

- [x] 1.1 In `docs/extending/architecture.qmd` § "The lifecycle reducer": add the event/intent/effect definitions, state that cositos reducer effects are transport commands (naming `Send`, `Listen`, `ApplyState`, `InvokeCustom`, `Error`) and that domain intents travel inside `custom` message content by convention, and cite membrane (phronemophobic, "How to build a functional UI library from scratch") alongside Redux and Elm
- [x] 1.2 In `docs/extending/architecture.qmd` § "The Document is the virtual DOM": add the UI-IR criteria checklist (lossless round-trip; inspectable/translatable without the source runtime; independent of source and target formats) framed as an evaluation rubric for Document-format changes

## 2. State-discipline cross-reference

- [x] 2.1 In `docs/using/state-discipline.qmd`: add a one-sentence cross-reference linking the rules to membrane's "parent is in charge" component principle (place near the top, in or after "The one-sentence discipline" section); link target is the series post (https://blog.phronemophobic.com/reusable-ui-components.html)
- [x] 2.2 (Optional) In `docs/using/glossary.qmd`: add short entries for **intent** and **effect** (as used in the new architecture vocabulary), linking to the architecture page

## 3. Authoring convention

- [x] 3.1 In `docs/using/authoring-widgets.qmd`: add a short "Intent-shaped custom messages" section documenting the `{event, ...}` dict-family convention (e.g. `{"event": "set", "path": [...], "value": ...}`), an MVU `update(msg, state)` example applying it, and the note that it is host-side only and inert on stock anywidget
- [x] 3.2 Verify the section's examples are consistent with `examples/widgets/button.js` and `examples/widgets/download_button.js` conventions (dict keyed on `event`)
- [ ] 3.3 In `docs/using/dashboard.qmd` (optional, task-level choice): link to the new convention section instead of restating it

## 4. Verification

- [ ] 4.1 Build the docs (`mise run docs`) and check the three pages render without warnings; visually confirm with `mise run qa-docs` — **blocked: quarto not installed on PATH**; structural checks done instead (anchors resolve, headings exist; see change log)
- [x] 4.2 Cross-check no code/protocol/fixture files changed (`git status` shows docs only)
