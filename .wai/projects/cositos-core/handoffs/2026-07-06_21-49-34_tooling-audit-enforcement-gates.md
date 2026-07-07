---
date: 2026-07-06T21:49:34-0300
git_commit: 7d7faba
branch: main
directory: ~/cositos
issue: cositos-83x (E3, filed); F19/F20 (tool report)
status: handoff
---

# Handoff: tooling-usage audit + enforcement gates (F19/F20 → E1/E2/E3)

## Context

This session was a **tooling-evaluation task**, not feature work on `cositos`. `cositos`
is the dogfooding project for the four `charly-vibes` CLIs — **wai** (workflow), **dont**
(record claims + ground them with file evidence), **pretender** (code-complexity gate),
and **ah**/**espectacular** (behavioural-spec verifier). The question asked: *were the
sessions that built cositos actually using pretender/espectacular/dont, and if not, why?*

The audit found two gaps, logged as **F19** and **F20** in `TOOL_EVALUATION.md` and the
published report. I then built the achievable enforcement (E1) into cositos, demonstrated
the dont ritual (E2), and filed the blocked follow-up (E3). All tool findings stay in the
report; only the cositos-project gate task went to beads (per the workspace's
tool-vs-project separation rule).

## Current Status

### Completed (committed)
- [x] **Audit** of the ~3 build sessions vs. tool on-disk state. Result:
  - **pretender** — used, gated, but frozen to Python+JS; **silently no-ops** on the
    later Julia/C#/R/Clojure cores (ships no grammar for them → scans 0 files, exit 0).
  - **espectacular** — used for Python protocol/serialization/embed; no spec ever written
    for the 4 new backends or `probe/`.
  - **dont** — effectively abandoned after day-1 init (stale 2-claim ledger, one a dummy);
    never wired into a gate, so it decayed. Root cause: **F1** (can't cite vendored
    `anywidget/`/`ipywidgets/` repos) + no enforcing gate.
- [x] **F19 + F20 + an "Enforcement" section** logged in `TOOL_EVALUATION.md` and mirrored
  (amnesia-test standard) into the published report — committed `fc88f2f` (cositos) and
  pushed to the `sandbox` repo (`de28b15`).
- [x] **E1 — coverage-manifest gate (live).** `coverage-manifest.toml` +
  `scripts/coverage_audit.py`, wired into `mise run verify` **and** lefthook pre-commit.
  Fails on an undeclared backend dir, or a dir claiming `pretender=true` that parses 0
  files (the F19 failure mode). Both failure modes were verified. Commit `fc88f2f`.
- [x] **E2 — grounding backfill (demonstrated).** Grounded the 3 real capability findings
  (IRkernel comm-open bug, .NET non-standard protocol, clojupyter no comm-open API) in
  `dont` against `probe/README.md`. Ledger now 4 verified claims. Commit `7d7faba`.
- [x] **E3 — filed as `cositos-83x`** (P2): wire `dont verify` into verify+pre-push once
  upstream F1 is fixed.

### Not mine / already resolved
- [x] **P0 `cositos-mx7` + P1 `cositos-d33`** (static-export view identity) were fixed by
  **concurrent work** (`baf8f71`) during this session — verified `with_view_identity()`
  is in `embed.py`, both issues closed. I did not touch them.

## Critical Files

1. `coverage-manifest.toml` — declares every backend dir's quality-tool coverage or an
   explicit `exempt` reason. **Edit this in the same commit when adding a new language.**
2. `scripts/coverage_audit.py` — the E1 gate logic (undeclared-dir + pretender-no-op checks).
3. `mise.toml` — `[tasks.coverage-audit]` and its entry in `[tasks.verify].depends`.
4. `lefthook.yml` — `coverage-audit` in `pre-commit` (no glob, always runs).
5. `AGENTS.md` (tail, "Quality-tool coverage & grounding rituals") — E1/E2/E3 for future sessions.
6. `TOOL_EVALUATION.md` (F19, F20, "Enforcement") + `../sandbox/charly-vibes-tools/dev-tooling-evaluation.md`.

## Key Learnings

1. **A tool stays used only if a gate fails when it's absent.** pretender/ah survived
   every session because they're in lefthook+verify; dont evaporated because nothing broke
   without it. This is the whole diagnosis of F20.
   - Evidence: `.dont/events.jsonl` had only `project.initialized`; `.pretender/history`
     shows active use.
2. **pretender silently succeeds on unsupported languages** (Julia/C#/R/Clojure) — the
   most dangerous failure mode because it *looks* covered. Root fix is upstream (exit
   non-zero on "0 files matched a supported grammar"); E1 is the project-side guard.
3. **dont F1 is the adoption blocker** but dont *is* usable against in-project evidence —
   E2 proved it (4 verified claims now). The vendored-repo citation gap remains upstream.

## Open Questions

- [ ] Should the day-1 dummy claim (`"good clean claim about protocol version two point
  one"`) be purged? `dont` has no claim-delete (only `undoubt`); tracked in `cositos-83x`.

## Next Steps

1. **Resume normal cositos work** — `bd ready` shows ~20 issues; next by priority are the
   P1s: `cositos-e4j` (Julia view-identity parity with the just-fixed mx7), `cositos-pvi`
   (qa-notebook has no widget frontend).
2. When adding any new backend language, **add its `coverage-manifest.toml` entry** or the
   pre-commit gate blocks the commit.
3. If upstream fixes dont F1, execute `cositos-83x` (the E3 dont gate).

## Artifacts

New files:
- `coverage-manifest.toml`
- `scripts/coverage_audit.py`

Modified files:
- `mise.toml`, `lefthook.yml`, `AGENTS.md`, `TOOL_EVALUATION.md`
- `.dont/db.cozo`, `.dont/tx.seq` (3 grounded claims)
- `../sandbox/charly-vibes-tools/dev-tooling-evaluation.md` (pushed)

## Related Links

- Prior handoff: `.wai/projects/cositos-core/handoffs/2026-07-06_21-07-27_multilang-backend-expansion.md`
- Enforcement design: `TOOL_EVALUATION.md` → "Enforcement — making the tools impossible to silently drop"
- Resume: `bd ready`, `mise run verify`, `wai status`, `dont list`.

## Additional Context

Gotchas carried forward: docs-only/non-`.py` commits can fail lefthook (F17) → the new
`coverage-audit` command has no glob so it *always* runs, which conveniently avoids the
all-skip exit-1 trap. Stage commits explicitly by path; concurrent sessions are active on
`main`, so `git pull --rebase` before pushing.
