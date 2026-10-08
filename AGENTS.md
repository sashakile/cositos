<!-- SPECODELIC:START -->
## Specodelic — spec format rules (managed block)

This repo's `specs/`-style markdown spec files (YAML frontmatter +
fixed-schema tables) are linted by `spk` (crates.io: specodelic).
Write specs so `spk lint` passes; embedded format revision: specodelic.md Revision 18

### Lint rules (every violation names its `rule_id`)

- `linter.frontmatter_valid` — frontmatter `kind` must be `intent` — the only top-level intent kind
- `linter.id_matches_file` — frontmatter `id` must equal the filename stem with `-` mapped to `.` (`_` is literal); a `spec.md` file derives its expected id from its parent directory (Revision 18)
- `linter.unique_id` — every row id in a file must be unique across all of the file's tables
- `linter.guard_required` — every transition must carry a non-null guard (a guard may be prose, or cite an invariant Constraint or a State — target typing is `ref_kind_compatible`'s beat)
- `linter.model_present` — the Model section must contain both a States list and a Transitions table (empty-but-present beats absent)
- `linter.ears_syntax` — the intent statement must contain an imperative `SHALL` and match one of the five EARS patterns
- `linter.no_conjoined_id` — an id must not encode two capabilities joined by `and`/`or`
- `linter.no_universal_in_id` — an id must not contain a universal token (all/every/any/always/never)
- `linter.total_refs` — every structured-field [[link]] must resolve to a definition somewhere in the corpus (Revision 18: all files resolve corpus-wide — the former `id: spec` self-containment retired)
- `linter.coverage` — every constraint must have a deriving property (`∃ property.derives_from == <constraint>`)
- `linter.no_orphan_property` — every property must derive from at least one constraint
- `linter.law_cases` — every law-kind property must enumerate its required cases as **name:** labels in its own predicate — the identity and associativity floor is mandatory, extra named cases are checkable declarations
- `linter.requirement_drift` — a dual-format file's ## Requirements mirror must hold every delta requirement (ADDED and MODIFIED sections alike) with identical requirement text, compared per requirement so mixed-delta files are satisfiable (blank lines and trailing space ignored)
- `linter.dual_format_valid` — a file carrying `## ADDED Requirements` must be a dual-format file — pair it with a sibling `## Requirements` section (Revision 18: the id is the naming law's business, not this rule's)
- `linter.terminal_states_emit` — every failure terminal state must emit exactly one file-owned effect Constraint — a mute failure terminal is a finding (specs/linter-failure_shape.md; timed_out/exploration_only are the stated v1 non-goal)
- `linter.error_labels_unique` — within one file, no two error Constraints may share a variant head — the label is file-id-namespaced (errors.md error_expr_shape), so collisions are a per-file property
- `linter.guard_negation_total` — every failure transition must cite exactly the union of its success siblings' citation sets, or be on the recorded carve-out list (orchestrate.md's stage-fail transitions) — a zero-citation failure guard off the list is a finding
- `linter.every_state_used` — every declared state must appear as from or to in at least one transition — a state no transition reaches is machinery the model can never enter or leave
- `linter.every_transition_valid` — every transition's from and to must name states declared in the same file's States section
- `linter.no_self_ref` — a row must not reference itself via traces_to or derives_from — a self-tracing row has no owning purpose
- `linter.acyclic` — the directed graph formed by constraint-traces_to ∪ property-derives_from ∪ guard-as-edge must contain no cycle (derives_from edges are property-sourced — the Reference Typing Appears-on column is normative, so a Constraint-row derives_from is typing's beat, never an edge)
- `linter.single_root_reachable` — every constraint/property/state/transition row must reach its file's OWN intent row through own-file primary linkage (traces_to/derives_from chains resolved within the file, plus the model's own from/to/guard/emits edges) — cross-file typed edges (guard citations of foreign constraints, satisfies, observes) are outbound leaves, never reachability paths; tiered: cross-file-only rows warn (advisory, exit 0), rows with no path to ANY intent hard-fail
- `linter.observability` — every effect Constraint must be the target of ≥1 `observes` reference from a different row — advisory: warned on the warnings channel (exit 0), never a failure
- `linter.checklist_well_formed` — a declared checklist manifest (`*.checklist.md`) must be a flat item list with stable ids plus a mapping table with exactly item/status/mapped_ids/rationale columns — a manifest the linter cannot read is a checklist going silently unconsulted
- `linter.every_item_accounted` — every checklist item must have exactly one mapping row with status `covered` or `waived` — an unconsulted item is the failure this checker exists to prevent
- `linter.covered_maps_resolve` — a `covered` mapping row must name a non-empty mapped_ids list whose ids resolve to real constraint or property rows — a claim resting on nothing is not a claim
- `linter.waiver_has_rationale` — a `waived` mapping row must carry non-empty rationale prose — an unexplained waiver is an unconsulted item with extra steps
- `linter.no_duplicate_claim` — no two mapping rows may target the same checklist item — one claim per item, on the record
- `linter.constraint_kind_closed` — every Constraint row's kind must be in {invariant, advisory, effect, extension_point} — an unreadable kind cell is outside the closed set (specs/linter-schema_shape.md)
- `linter.property_kind_closed` — every Property row's kind must be in {unit, law} — an unreadable kind cell is outside the closed set (specs/linter-schema_shape.md)
- `linter.pack_shape` — a kind: profile pack file's manifest must carry all six facet tables (Sections/Kinds/References/Checkers/Floors/Requires) with well-formed two-column rows, its Kinds rows must be pack-qualified (never a base closed-set name — the narrowing rejection), and manifest tables may not appear on non-profile files (specs/packs.md, Revision 14)
- `linter.orphan_vocabulary` — orphan vocabulary is a labeled failure naming the candidate pack and both remediations (enable/declare the pack, or fix the vocabulary) — a declared uses edge targeting an id no discovered kind: profile pack carries, or a pack-qualified token used in a kind/field position with no discovered pack in its namespace (candidate prefix-derived when only the namespace is known) (specs/packs.md, Revision 14)
- `linter.skew_advisory` — a declared pack's Requires base pin older than the workspace corpus revision is a warnings-channel advisory naming the pack's base pin and the corpus revision — never silent, never failing (specs/packs.md, Revision 14)
- `linter.schema_matches_typing_table` — when the lint target carries the format doc, its Reference Typing table must equal the Schema value row for row — the document and the code cannot drift; a corpus without the format doc is out of the gate's scope (no-op, never fabricated expected rows) (add-acset-core, linter-schema_shape family)

### Commands

- `spk lint <dir>` — check the invariants (fails with a hint on zero files)
- `spk graph <dir>` — typed reference graph (state edges, typing
  violations, supersedes cycles; blast-radius lands later)
- `spk compile <files>` — emit TOML / proptest / TLA+ artifacts
- `spk model-check <files>` — run the model checker against compiled
  output (stateright; reports land as `*.check.json`)
- `spk explain [topic]` — the embedded format primer (works offline)
- `spk doctor` — diagnose workspace + block currency
- `spk feedback bug --dry-run` — file an issue against upstream

Refresh this block after upgrading: `spk init --force`.
<!-- SPECODELIC:END -->

<!-- DONT:START -->
# DONT MANAGED BLOCK — DO NOT EDIT

This project uses `dont` for grounded-claim workflow.

At session start run `dont prime --json`.

Canonical agent instructions: `.dont/AGENTS.md`.

Edits inside this managed block will be overwritten by `dont doctor --fix`.
<!-- DONT:END -->

<!-- WAI:START -->
# Workflow Tools

This project uses **wai** to track the *why* behind decisions — research,
reasoning, and design choices that shaped the code. Run `wai status` first
to orient yourself.

## Quick Start

1. `wai sync` — ensure agent tools are projected
2. `wai status` — see active projects, phase, and suggestions

When context reaches ~40%: stop and tell the user — responses degrade past
this point. Recommend `wai close` then `/clear` to resume cleanly.
Do NOT skip `wai close` — it enables resume detection.

## Autonomous Work Policy

Proceed without routine confirmation when the next step is clear.
Do not ask to continue, fix, or commit — just do it.

**Stop and ask** only when:
- Conflicting requirements or ambiguous intent
- Destructive actions (data loss, force-push, drop table)
- Credentials, secrets, or external services not yet authorized
- Unresolved test failures after two attempts
- Push, deploy, or release — always get explicit authorization
- Context approaching 40% — recommend `wai close` then `/clear`

## Detailed Instructions

Full workflow reference — session lifecycle, capturing work, command cheat
sheets, cross-tool sync, and PARA structure — lives in **`.wai/AGENTS.md`**.
Read it at the start of your first session or when you need detailed guidance.

Keep this managed block so `wai init` can refresh the instructions.

<!-- WAI:END -->

<!-- WAI:REFLECT:REF:START -->
## Accumulated Project Patterns

Project-specific conventions, gotchas, and architecture notes live in
`.wai/resources/reflections/`. Run `wai search "<topic>"` to retrieve relevant
context before starting research or creating tickets.

> **Before research or ticket creation**: always run `wai search "<topic>"` to
> check for known patterns. Do not rediscover what is already documented.
<!-- WAI:REFLECT:REF:END -->

<!-- ah:managed:start -->
## espectacular

Run `ah check` to verify spec-test correspondence before committing.

- `ah check` — validate all deployed specs
- `ah check --changes <name>` — validate with a change overlay
- `ah init` — set up or refresh espectacular project files
- `ah doctor` — diagnose setup issues
- `ah explain <topic>` — playbook guidance for finding kinds and suggested actions
- `ah doctor --enable <adapter>` — write adapter config into .espectacular/config.toml
- `ah signals` — emit dont drift signals
<!-- ah:managed:end -->

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->

<!-- TICKET WORKFLOW (not tool-managed) -->
## Ticket implementation workflow

**This is the main development loop.** For every ticket (beads issue): implement
using TDD (red → green → refactor) → invoke `/rule-of-5-universal` → fix all
findings → commit → move to the next ticket. Do not start the next ticket until the
current one is committed and clean. **No batching across tickets.**

Concretely, per ticket:

1. **Claim** — `bd update <id> --claim` (check `metadata.files` for conflicts first).
2. **TDD** — write a failing test, make it pass, refactor. ARRANGE-ACT-ASSERT
   (unit/integration) or GIVEN-WHEN-THEN (behaviour). No mocks — prefer real
   fakes/fixtures.
3. **Review** — invoke `/rule-of-5-universal` on the result and fix every finding
   before committing.
4. **Gate** — `mise run verify` must pass (lint, typecheck, coverage, complexity,
   specs, coverage-audit). Structural changes commit separately from behaviour changes
   (Tidy First).
5. **Commit** — atomic and revertible; stage explicitly by path (never `git add -A`).
6. **Close** — `bd close <id>`, then start the next ticket. If the ticket surfaced
   tooling friction, log it as an `F#` finding in `TOOL_EVALUATION.md`.

<!-- COVERAGE & GROUNDING RITUALS (not tool-managed) -->
## Quality-tool coverage & grounding rituals

These enforce that the charly-vibes tools stay used as the project grows
(see `TOOL_EVALUATION.md` F19/F20 and the "Enforcement" section).

- **Coverage manifest (E1).** Every backend directory must be declared in
  `coverage-manifest.toml` with a `pretender`/`espectacular` binding or an explicit
  `exempt = "<reason>"`. `mise run coverage-audit` (in `verify` + pre-commit) fails on
  any undeclared dir and on any `pretender = true` dir that parses zero files. **When you
  add a new language backend, add its manifest entry in the same commit.**
- **Grounding (E2).** For every empirical capability finding (kernel behaviour, upstream
  bug, protocol quirk), record a `dont` claim grounded in in-project evidence (research
  docs, `probe/README.md`, source). At handoff, the summary must list each finding and
  whether it was grounded. Citing the vendored `anywidget/`/`ipywidgets/` repos is still
  blocked upstream (F1); ground against in-project artifacts until that is fixed.
- **After F1 is fixed (E3):** add `dont verify` (no ungrounded/unverified claims) to
  `mise run verify` and pre-push, mirroring how `pretender`/`ah` are gated.

## Git & Workflow Discipline

- **Never use `git add -A`** — always stage specific files with explicit paths
- **Per-ticket pipeline**: always follow `TDD → ro5u → fix → commit → next ticket`
