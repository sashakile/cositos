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
