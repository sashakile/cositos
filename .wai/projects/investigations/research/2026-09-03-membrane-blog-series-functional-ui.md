# The phronemophobic blog series: grounding "How to build a functional UI library from scratch" in cositos

**Date:** 2026-09-03
**Kind:** advisory research — no code changes proposed yet
**Extends:** [`2026-08-28-what-cositos-can-learn-from-phronmophobic-membra.md`](2026-08-28-what-cositos-can-learn-from-phronmophobic-membra.md) (repo-level memo; that doc covered the membrane README and the MembraneChannel idea — this doc adds the design-rationale essays and grounds each idea against the current implementation)

## Source

Blog series "How to build a functional UI library from scratch", blog.phronemophobic.com — four posts:

| # | Post | Core contribution |
|---|------|-------------------|
| I | [What is a User Interface?](https://blog.phronemophobic.com/what-is-a-user-interface.html) | Definitions: **event → intent → effect**; UI = two pure functions (event fn, view fn); critique of OO platform toolkits (stateful `preventDefault`, global event state, opaque components). |
| II | [Implementing a Functional UI Model](https://blog.phronemophobic.com/ui-model.html) | Views are plain data (records + vectors); generic inspection (`origin`/`bounds`/`children`); pluggable event model; handlers **return intents**; parents transform child intents ("functional bubbling"). |
| III | [Reusable UI Components](https://blog.phronemophobic.com/reusable-ui-components.html) | Intents carry **references** into state (`$num` → specter paths); built-in `:get/:set/:update/:delete` effects by reference; **incidental vs. essential state** (parent decides; private state stays inspectable as data under a `:private` key); contextual state (focus); property-based UI testing; framework converters (re-frame/fulcro/cljfx). |
| IV | [The HTML Tax](https://blog.phronemophobic.com/html-tax.html) | HTML as lossy, browser-bound data; argues for a **UI intermediate representation** (LLVM-IR analogy) between design tools and platform targets, with criteria for a good UI format. |

Why this matters for cositos: our core already converges on the same primitives (pure reducer returning effects, plain-data Documents, thin per-host seams). The essays supply the *missing design vocabulary and component-level patterns* that our repo-level memo did not capture. Each idea below is grounded against the current implementation before being recommended.

## Grounded findings

Each finding states the blog idea → the cositos evidence it lands on → verdict.

### F1. The intent/effect distinction is missing from our docs vocabulary — cheap docs win

**Blog:** Post I separates *intent* (data describing what the user wants, returned by event handlers) from *effect* (carrying out the intent) and defines an impure *effect handler* at the edge.

**Grounding:** `src/cositos/lifecycle.py` uses "effects" for what membrane would call two different things: the reducer's *commands to the shell* (`Send`, `Listen`, `ApplyState`, `InvokeCustom`, `Error` — lifecycle.py:57–95) and the shell's *execution* (`WidgetShell._exec_one`, lifecycle.py:411 — the membrane "effect handler"). Meanwhile `SendState`/`ApplyState` are transport-shaped, not intent-shaped: the reducer emits "send this state dict", never "the user wants to change value X".

**Verdict: adopt in docs.** Add the event/intent/effect vocabulary to `docs/extending/architecture.qmd` (§ "The lifecycle reducer" already cites Redux/Elm; add membrane as third convergent data point) with one clarifying paragraph: cositos's reducer effects are *transport commands*, and domain intents are carried inside `custom` message content by convention. Zero code change.

### F2. "Parent is in charge" — already true in the core; worth citing, not building

**Blog:** Post II/III's core component principle: parents may alter/ignore child intents; event handlers must be pure so parents retain the final word (the functional replacement for `stopPropagation`).

**Grounding:** cositos already enforces a strict version of this at the transport boundary: the reducer — not the shell — decides effects from capability flags ("the shell never blocks or rewrites events based on capabilities", `TransportCapabilities` docstring, lifecycle.py:43–45; `supports_receive` gate at lifecycle.py:215 suppresses `Listen` for one-way hosts). On the frontend side, `docs/using/state-discipline.qmd` Rule 1–3 (one model as source of truth, views as pure projections, no widget-to-widget `link`/`observe`) is the same "parent in charge" discipline with measured evidence (`links_kept = 0` across every scenario).

**Verdict: adopt in docs only.** A cross-reference in `state-discipline.qmd` ("this is the measured version of membrane's 'parent is in charge' component principle") strengthens both docs. No design change needed.

### F3. References in intents ($ref → path) — maps to app-level custom-message convention, NOT the wire protocol

**Blog:** Post III's biggest mechanism: event handlers return intents that reference *where* the change belongs (`[::toggle $checked?]`), with built-in `:get/:set/:update/:delete` effects resolving those references (specter paths). This decouples reusable components from state layout.

**Grounding (and the honest limit):** the cositos wire protocol cannot adopt this. It is anywidget-compatible (`_model_module = "anywidget"` identity at lifecycle.py:147–166, pinned to `~0.11.*`), and anywidget `update` messages carry top-level-key state dicts — the front `Model` merges inbound updates per top-level key (`#receive`) and sends dirty top-level keys (`save_changes`, model.js:95–102). There are no key-path updates on the wire (paths exist only for buffers, per protocol v2; `build_update(state)` takes a flat state dict, protocol.py:69). Membrane's `defui` macro traces derived values to component arguments — work we'd have to do explicitly in Python.

**Verdict: adopt as an authoring convention, not protocol machinery.** The wire protocol itself is unchanged — this is convention, not machinery. The useful residue: a documented *recommended shape for `msg:custom` content* so app-level intents stay reusable and host-side MVU `update` functions can apply them generically (mirroring `docs/using/state-discipline.qmd`'s `update(msg, state)` skeleton). Belongs in `docs/using/authoring-widgets.qmd` or the dashboard tutorial. **Resolved by Q1 check (2026-09-03): the convention must extend the existing `{"event": ...}` dict style, not replace it** — see open question 1 for evidence.

### F4. Incidental vs. essential state — a real, small design gap on the frontend

**Blog:** Post III: whether subcomponent state is incidental is the *consumer's* decision; private state must remain inspectable data (stored under a `:private` key), never hidden — otherwise debugging/testing becomes misery (their footnote: Chrome Autofill).

**Grounding:** two real gaps in cositos:

1. `front/src/model.js` holds state in JS private fields (`#state`, `#dirty` at model.js:60–63). It's the only state holder, so it's *small*-hidden, but it is not data you can inspect, serialize, or snapshot-test — membrane's point exactly.
2. Widget-*view* state (scroll, focus, text cursor, selection) lives in the anywidget views' DOM, outside both the Model and the Document. Membrane's "UI state as well-defined data" is only achievable for *widget state* (which the Document captures — `docs/extending/architecture.qmd` § "The Document is the virtual DOM"), not view state. View state is unserializable for us because we reuse the anywidget frontend verbatim (deliberate trade, architecture.qmd § "Why reuse the anywidget frontend verbatim").

**Verdict: partial adopt, needs a design decision.** Options: (a) docs-only — a convention reserving a namespaced key for widget-local incidental state so it round-trips through Documents while staying distinguishable; (b) larger — have cositos views mirror incidental view state (focus/scroll) into the Model. Option (b) violates "reuse the anywidget frontend verbatim" for little gain. **Recommend (a)**, filed as a question for planning, not committed. **Resolved by Q2/Q3 checks (2026-09-03): the key must NOT be `_`-prefixed** — underscore keys already carry ecosystem meaning (`_esm` protocol.py:25, `_css` protocol.py:26, `_model_*` identity lifecycle.py:147) — a plain namespaced key such as `"ui_state"` is safer. See open questions 2–3 for mechanics and the residual verification item.

### F5. Property-based testing over view data — mostly already done; one extension worth noting

**Blog:** Post III: because views are data, you get generative tests — round-trip losslessness, bounds, overlap, contrast — "testing UI code is just like testing any other domain."

**Grounding:** cositos already has the core of this: `tests/test_serialize.py` uses Hypothesis (`@given`, test_serialize.py:5–6) for round-trip properties, and the golden-fixture conformance suite (`fixtures/*.json`, `tests/test_conformance.py`) is exactly post IV's "inspection without a browser" criterion. What we *cannot* do is view-level assertions (bounds/overlap/contrast) — we don't render; the anywidget frontend does.

**Verdict: already covered at the data level; view-level is out of scope.** Cite in `specs.qmd` prose if a natural place appears. No action.

### F6. The IR criteria (post IV) — validation for "the Document is the virtual DOM"

**Blog:** Post IV proposes a UI intermediate representation (LLVM IR analogy) judged on: lossless, inspectable/translatable without the source runtime, independent of source and target formats.

**Grounding:** cositos already built this and says so in different words — the Document as "a plain-data description of the UI, decoupled from any particular runtime" serving live-replay and static-export backends (architecture.qmd § "The Document is the virtual DOM"); the contract-as-fixtures section is "reference implementation + losslessness" in IR clothing.

**Verdict: adopt in docs.** Add the IR criteria as a checklist in the architecture page's Document section — it sharpens the existing argument and gives future Document-format changes an evaluation rubric.

## What we are NOT lifting (and why)

| Blog machinery | Why not |
|---|---|
| Own graphics model (records, draw functions, event loop) — post II | We don't own rendering or the draw loop; the anywidget frontend does. Context, not leverage. |
| `$ref`-tracing `defui` macro — post III | Macro-based compile-time tracing has no Python analog; the F3 convention gets the decoupling benefit at negligible cost. |
| Bubbling machinery (`wrap-on`, `-bubble` protocols) — post II | We don't nest interactive components in a retained tree; our "bubbling" is the reducer's capability gate (F2) and the MVU update function. |
| The HTML Tax's transpilation argument — post IV | We're guests in browser-hosted fronts regardless; only the IR criteria (F6) carry over. |
| MembraneChannel for Clojure hosts — 2026-08-28 memo finding 3 | Still valid and untouched by this series; it leverages membrane's *code*, not these essays. |

## Recommendations (ranked)

1. **Docs: intent/effect vocabulary + membrane citation in `architecture.qmd`** (F1, F6). One editing pass, no risk.
2. **Docs: cross-reference "parent is in charge" in `state-discipline.qmd`** (F2). One sentence + link.
3. **Decide, then document: custom-message intent convention extending the `{event, ...}` dict family** (F3 → open question 1, resolved: no conflicts). Shape refinement settled (extend `{"event": "set", "path": [...], "value": ...}`, don't introduce tuples); remaining decision is only whether to write it into `authoring-widgets.qmd` now or after real usage pressure.
4. **Decide, then document: reserved private-state key** (F4 → open questions 2–3, resolved: mechanically safe; must be plain-key, not `_`-prefixed). Remaining decisions: export behavior (feature vs. filter in `dump_model`) and the stock-AnyModel arbitrary-key verification.

## Grounding table (E2 ritual)

| Finding | Empirical claim | Grounded? | Evidence |
|---|---|---|---|
| F1 | Effects/commands dual use of "effect" in lifecycle.py | ✅ in-project | lifecycle.py:57–95, 411 |
| F2 | Reducer decides effects from capabilities; shell doesn't branch | ✅ in-project | lifecycle.py:43–45, 215 |
| F3 | Wire updates are top-level-key dicts; no key-path updates | ✅ in-project | front/src/model.js (`save_changes` :95–102, `#receive`); protocol.py:69 (`build_update`) |
| F4 | Front Model state hidden in JS private fields; view state outside Document | ✅ in-project | front/src/model.js:60–63; architecture.qmd § Document |
| F5 | Hypothesis round-trip + golden fixtures already exist | ✅ in-project | tests/test_serialize.py:5–6; fixtures/, tests/test_conformance.py |
| F6 | Document already plays the UI-IR role | ✅ in-project | architecture.qmd § "The Document is the virtual DOM" |
| — | Membrane behaviours (bubbling, defui tracing, effect registry) | n/a — external | blog posts I–IV; cited, not reproduced |

## Open review questions before planning

Resolved 2026-09-03 by grounding against the implementation:

1. **Contrib/example `msg:custom` conflict? — No conflict; the convention must extend, not replace, the existing shape.** `src/cositos/contrib/` uses no custom messages at all (controls.py, harvest.py: zero `send_custom`/`msg:custom` references). The only senders in the repo are example widgets: `examples/widgets/button.js:13` sends `{ event: "click" }` and `examples/widgets/download_button.js:35` sends `{ event: "download", filename, href }` — flat dicts keyed on `event`. Tests use `{"kind": "ping"}` (test_shell.py:110) — also dict-based. **Conclusion: frame the F3 convention as an extension of this `{event, ...}` dict family (e.g. `{"event": "set", "path": [...], "value": ...}`) rather than the `[type, path, value]` tuple from the earlier draft.**
2. **Private-state key mechanics — works with zero special-casing, but two caveats.** (a) `SendState(include=…)` filters top-level keys generically (lifecycle.py:204–212; `test_filtered_send_state_omits_identity`, test_lifecycle.py:160–170) — a reserved key behaves like any other: included in full sends, excluded from filtered sends unless named. Semantics need one doc sentence, not code. (b) Static export: `dump_model` preserves state verbatim (serialize.py:100–104), so private state rides into published HTML — a *product decision*: treat as a feature (UI state restored on reload) and document it, or exclude it from export (requires a filter in `dump_model`). (c) **Do not use a `_` prefix**: underscore keys already carry meaning (`_esm`, `_css`, `_model_*`); a plain namespaced key avoids collision.
3. **Stock-anywidget fit — both conventions are transport-compatible by construction, with one residual verification.** Custom messages are opaque end-to-end: the frontend just emits `msg:custom` with the content (model.js:122–124) and the kernel side routes to `on_custom` untouched (lifecycle.py `InvokeCustom`) — zero frontend or kernel machinery; on stock anywidget the convention is simply inert. The private-state key rides standard top-level-key `update` messages (`save_changes`, model.js:95–102; `build_update` flat dict, protocol.py:69) — also zero machinery. **Residual item (external verification):** how the *published* anywidget AnyModel treats unknown/undeclared state keys on `comm_open`/`update` — the oracle test only asserts the overlapping protocol surface (target, identity, update shape; test_oracle_anywidget.py:8–11) and doesn't cover arbitrary-key tolerance. If stock AnyModel rejects undeclared keys, the private-state convention is cositos-frontend-only and must be documented as such.

## Bottom line

Four adopt-as-docs items, zero protocol changes, and all three pre-planning questions now resolved by grounding (2026-09-03): Q1 found no conflicts but reshaped the F3 convention to the existing `{event, ...}` dict family; Q2 found the private-state key needs no code but is a product decision at the static-export boundary and must not use a `_` prefix; Q3 confirmed both conventions need zero frontend/kernel machinery, leaving one external verification (stock AnyModel arbitrary-key tolerance). The series' value to cositos is vocabulary (intent/effect), one component principle (parent in charge — already practiced, now citable), two authoring conventions (intent-shaped custom messages, inspectable private state), and a validation of the Document-as-IR architecture. Nothing in the essays changes the core; everything lands in docs or conventions.

**Revisit trigger:** if the anywidget frontend contract ever ships key-path (nested) state updates, or the Document format gains path-level addressing, re-open F3 and F4 — both verdicts would flip from "convention" to "protocol".
