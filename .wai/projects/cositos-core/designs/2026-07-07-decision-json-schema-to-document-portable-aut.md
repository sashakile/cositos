# Decision: `json_schema_to_document` portable auto-widget — **DEFER**

- **Ticket:** cositos-ay3.4 (decision) · parent epic cositos-ay3 (widget state-management)
- **Date:** 2026-07-07
- **Status:** Decided — **DEFER** (do not build the portable certified core now)

## The question

Should cositos build a portable, fixture-certifiable
`json_schema_to_document(schema) -> Document` as a language-neutral *auto-widget* core —
each backend emits JSON Schema from its native types (pydantic / dataclass / C# records /
Julia structs), and the shared function turns that schema into a cositos `Document`
(widget-state envelope)? Or defer it per YAGNI, keeping rich per-type ergonomics in
per-language contrib?

## What a `Document` actually is (grounding)

A `Document` (`src/cositos/serialize.py`) is the ipywidgets **Widget State JSON v2**
envelope: `{version_major, version_minor, state}` where `state` maps each `model_id` to a
record `{model_name, model_module, model_module_version, state: {...}}`. Crucially, a model
record carries an **`_esm`** — the anywidget ES-module that *renders* the widget. A
`Document` with no `_esm` that understands the schema is just data, not a rendered widget.

## Why defer

1. **No consumer (YAGNI).** Nothing in the repo, the ay3 benchmark study, or the
   state-discipline guide asks for schema-driven widget generation. The ay3 epic's grounded
   conclusion is about *state topology* — "single Model / tracked DAG with shared
   derivations; no peer links" (`docs/explanation/state-discipline.qmd`) — not input/widget
   generation. `json_schema_to_document` is tangential to what the research concluded cositos
   needs.

2. **The valuable pieces are explicitly out of the certifiable core.** The auto-widget value
   lives in two parts that the portable core cannot own:
   - **Per-language type → JSON Schema extraction** (pydantic, C# records, Julia structs).
     The ticket itself scopes "rich per-type ergonomics stay per-language contrib," and the
     founding design already lists this as a v0 **non-goal**: *"Observer autodetection
     (traitlets/psygnal/pydantic) — host ergonomics, added per host"*
     (`.wai/projects/cositos-core/designs/2026-07-03-design-cositos-a-portable-anywidget-backend.md`).
   - **A frontend form renderer** — the `_esm` that draws inputs from the schema. cositos
     tenet 3 is *"Reuse the frontend verbatim. No new JS."* A schema-form renderer is new
     frontend code; shipping it (or depending on an external schema-form library) breaks the
     "zero frontend maintenance" premise and the protocol-core identity.

   The portable middle (schema JSON → state skeleton) is the *low-value* slice; it delivers
   little without the two out-of-scope halves.

3. **5-language certification tax on speculative work.** Every core capability must round-trip
   byte-for-byte across all five ports (Python/Julia/C#/Clojure/R) against golden fixtures
   (`fixtures/*.json`; e.g. `julia/test/runtests.jl` conformance). JSON Schema is a large,
   evolving spec; certifying even a subset across five languages is a heavy, ongoing cost.
   Paying it before a single consumer exists is premature.

4. **Scope creep risk.** A schema→widget generator pushes cositos from *"the core owns the
   protocol, not the bindings"* toward being a UI/form framework — the exact responsibility
   the founding design was built to avoid.

5. **Could contradict the epic's own conclusion.** A naïve mapping (one widget per schema
   field) produces a *tree of peer widgets* — precisely the pattern the ay3 benchmarks found
   worse (peer links don't survive static export; state tangles). A correct mapping would have
   to target a **single Model** with a form `_esm`, which is more design than a "just map the
   types" framing implies.

## Options considered

| Option | Summary | Verdict |
|---|---|---|
| **A. Build the portable certified core now** | Ship `json_schema_to_document` + a schema-form ESM, certified in 5 langs | **Rejected** — no consumer; requires new frontend JS (breaks tenet 3); heavy 5-lang cert tax; scope creep |
| **B. Defer** | Keep it out of core; revisit on real demand | **Chosen** |
| **C. Python-only contrib spike when demand appears** | Prototype `cositos.contrib.autoform(schema)` (Python-only, like `harvest`) over an existing JS schema-form renderer; promote to a certified core only if a *second* language needs the identical mapping | **Sanctioned path** for when B's trigger fires |

Option C mirrors how the project actually grew: prove ergonomics cheaply and per-host first
(`cositos.contrib.harvest` is Python-only, optional, never in core), and only promote a
mechanism to the fixture-certified core once a second language demonstrably needs the *same*
thing (as transports did after the core proved out).

## Revisit trigger

Reopen this decision when **all** of the following hold:
1. A concrete consumer wants auto-widgets-from-types in **≥2 backend languages**, and
2. A frontend schema-form renderer exists that cositos can reference **without** taking on
   frontend maintenance, and
3. The mapping can target a **single Model** (consistent with the ay3 state-discipline
   conclusion), not a peer-widget-per-field tree.

Until then, anyone who needs it takes Option C (a Python-only `contrib` spike).

## Consequences / follow-ups

- **Per the acceptance criteria** ("if build, a follow-up feature ticket and OpenSpec change
  are filed"): decision is *defer*, so **no** feature ticket or OpenSpec change is filed now.
- The revisit trigger above is the documented condition; Option C is the cheap first step.

