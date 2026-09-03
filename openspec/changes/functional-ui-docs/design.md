## Context

The 2026-09-03 research doc (`.wai/projects/investigations/research/2026-09-03-membrane-blog-series-functional-ui.md`) grounded four blog essays against the implementation. Findings F1, F2, F3, F6 resolve to documentation changes; all pre-planning questions were answered by grounding (see the research doc's resolved "Open review questions"). No code or protocol changes are involved.

Current state of the docs being touched:

- `docs/extending/architecture.qmd` § "The lifecycle reducer" cites Redux and Elm as prior art and uses "effects" for the reducer's transport commands; `SendState`/`ApplyState` are transport-shaped, not intent-shaped.
- `docs/extending/architecture.qmd` § "The Document is the virtual DOM" describes the Document as plain-data UI description but offers no evaluation criteria for format changes.
- `docs/using/state-discipline.qmd` states "parent is in charge" rules with benchmark evidence but no theoretical lineage.
- `docs/using/authoring-widgets.qmd` does not document any `msg:custom` content convention; the de facto convention in `examples/widgets/` is flat dicts keyed on `event` (`{"event": "click"}`, `{"event": "download", filename, href}`).

## Goals / Non-Goals

**Goals:**

- Give the docs the event/intent/effect vocabulary, with membrane as a cited convergent prior art (F1).
- Add the UI-IR criteria as a reusable evaluation rubric for Document-format decisions (F6).
- Connect the measured state-discipline rules to membrane's "parent is in charge" principle (F2).
- Document a recommended intent-shaped `msg:custom` convention that *extends* the existing `{event, ...}` dict family (F3).

**Non-Goals:**

- No code, protocol, fixture, or test changes; no wire-format impact.
- No private-state key convention (F4) — gated by the stock-AnyModel arbitrary-key verification and an export-behavior product decision; tracked separately.
- No membrane-specific machinery in the core (bubbling, `$ref` tracing, own graphics model — explicitly rejected in the research doc's "What we are NOT lifting" table).

## Decisions

- **D1 — Vocabulary placement: architecture.qmd reducer section, not a new page.** The vocabulary clarifies existing text (effects list, shell execution); a new page would fragment the story. Membrane joins Redux/Elm as a third convergent citation, which strengthens the "why a pure reducer" argument flagged by the 2026-08-28 memo.
- **D2 — Distinguish "effects = transport commands" from "intents = domain data".** The doc states that cositos reducer effects are transport commands (`Send`, `Listen`, `ApplyState`, `InvokeCustom`, `Error` — `src/cositos/lifecycle.py:57–95`) and that domain intents travel inside `custom` message content by convention. Alternative considered: renaming lifecycle effects to "commands" — rejected: churn across code, fixtures, specs, and four language ports for zero behavior gain.
- **D3 — IR criteria as a checklist inside the Document section.** Criteria: lossless round-trip; inspectable/translatable without the source runtime; independent of source and target formats. Alternative considered: separate essay page — rejected: the criteria only matter where Document decisions are made.
- **D4 — Intent convention extends the existing `{event, ...}` dict family, not a new tuple shape.** Evidence: `examples/widgets/button.js:13`, `examples/widgets/download_button.js:35`, tests (`test_shell.py:110`). Documenting `{"event": "set", "path": [...], "value": ...}` style keeps authoring guidance consistent with shipped examples and lets MVU `update(msg, state)` apply intents generically. Alternative considered: membrane's `[type, path, value]` vectors — rejected: contradicts existing examples.
- **D5 — Convention is documented as host-side only, degrading gracefully.** Custom messages are opaque end-to-end (frontend emits `msg:custom` verbatim, kernel routes to `on_custom` untouched), so the convention needs zero frontend/kernel machinery and is inert on stock anywidget.

## Risks / Trade-offs

- [Docs drift from code if effect types change] → The architecture page already names effect types; keep names in sync via the existing spec docs, note file:line references sparingly to avoid staleness.
- [Convention doc contradicts future contrib widgets] → The convention is *recommended*, not enforced; examples in `authoring-widgets.qmd` should link to `examples/widgets/` as the reference.
- [Docs drift between `authoring-widgets.qmd` and the dashboard tutorial] → Document the convention once in `authoring-widgets.qmd`; have the tutorial link to it rather than restate it.

## Migration Plan

Docs-only edit pass; publish with the normal docs build. No rollback concerns beyond reverting the commit.

## Open Questions

- Exact placement of the intent-convention example: `authoring-widgets.qmd` is the primary target (proposal D4); whether `dashboard.qmd` also gets a worked example is a task-level choice left to implementation.
