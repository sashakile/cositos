---
tags: [publish-readiness, bd, dont, rule-of-5]
---

# Publish-readiness review—2026-07-07

Two Rule-of-5 reviews, both feeding epic `cositos-dad`:

1. A review of the contribution-enablement plan, re-scoped to *"prepare before
   making cositos public into a remote."*
2. A review of the resulting Beads epic/tickets themselves (issue-review skill).

This doc is the persisted evidence trail (ALIGN-001 fix—the original
Rule-of-5 output existed only in chat and wasn't retrievable across sessions).

## Review 1—Publish-readiness (contribution plan)

**Lens:** is the repo safe/clean to expose on a public remote, before any
contribution-UX work.

### Evidence gathered
```bash
git status --short            # .dont/db.cozo, .dont/tx.seq modified; 1 untracked research file
git ls-files | rg '^\.dont/'   # db.cozo, db.cozo.lock, tx.seq, events.jsonl, config.toml, AGENTS.md, seed/ all tracked
git grep -n "sasha"          # 4 hits, all in .wai/projects/cositos-core/handoffs/*.md
git grep -niE "api[_-]?key|secret|token|password|BEGIN (RSA|OPENSSH|PRIVATE)" -- .   # no real secrets found
ls .github                     # not found—no CI
fd -d1 "CONTRIBUTING|CODE_OF_CONDUCT|SECURITY" .   # none exist
rg -n "anywidget|Copyright|License" front/src/*.js  # conceptual references only, no vendored code found
```

### Findings

| ID | Severity | Finding | Ticket |
|---|---|---|---|
| CORR-001 | CRITICAL | `.dont/db.cozo` (114KB binary) + `tx.seq`/`events.jsonl` tracked and dirty; no equivalent exclusion to `.beads/`'s | cositos-dad.1 |
| CORR-002 | HIGH | No CI—`mise run verify` never runs automatically | cositos-dad.2 |
| CORR-003 | MEDIUM | `bd` Dolt sync depends on a remote that doesn't exist; never exercised | cositos-dad.9, .12 |
| CLAR-001 | MEDIUM | 4 files leak local username/path (`sasha`) | cositos-dad.3 |
| CLAR-002 | MEDIUM | No CONTRIBUTING/CODE_OF_CONDUCT/SECURITY | cositos-dad.4 |
| CLAR-003 | LOW | README doesn't state maturity/contribution expectations | cositos-dad.8 |
| EDGE-001 | HIGH | No explicit statement that anywidget/ipywidgets source isn't vendored | cositos-dad.5 |
| EDGE-002 | MEDIUM | `mise.toml` never spot-checked for machine-specific paths | cositos-dad.6 |
| EDGE-003 | LOW | Working tree dirty (uncommitted `.dont` changes + untracked research note) | cositos-dad.7 |

**Verdict:** NEEDS_REVISION. No leaked secret, but tracked binary DB + absent CI
are cheap to fix now, expensive after the repo is forked.

## Review 2—Issue-tracker review of the resulting epic

**Lens:** are the 14 tickets created from Review 1 complete, correctly scoped,
correctly ordered, and executable.

### Findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| PRE-001 | MEDIUM | All 14 tickets missing `metadata.files` | Backfilled on all tickets |
| CLRT-001 | MEDIUM | `cositos-dad.13` had no acceptance criteria | Split (see SCOPE-001), moot |
| CLRT-002/003 | LOW | Ambiguous doc-location / README-vs-NOTICE wording | Disambiguated (docs/bd-sync.md; NOTICE file) |
| SCOPE-001 | MEDIUM | `cositos-dad.13` bundled 4 design-heavy deliverables | Split into cositos-dad.15/.16/.17/.18; `.13` closed (superseded) |
| DEP-001 | HIGH | `cositos-dad.1` (P0) blocked by `cositos-dad.10` (P2)—priority inversion | `.10` and `.9` bumped to P0 |
| DEP-002 | LOW | `cositos-dad.11` depends on 8 tickets (bottleneck) | Confirmed intentional, no change |
| DEP-003 / EXEC-001 | HIGH | No ticket owned "decide target remote org/name/visibility"—`cositos-dad.11` unexecutable as written | Added `cositos-dad.14`, wired as a dependency of `.11` |
| ALIGN-001 | MEDIUM | Review reasoning existed only in chat, not persisted | This document |
| EXEC-002 | LOW | `cositos-dad.3` didn't enumerate the 4 file paths | Description updated with explicit list |

**Verdict:** NEEDS_UPDATES → all listed fixes applied same session.

## Current epic shape (post-fix)

```
cositos-dad.14 (decide remote target)  ─┐
cositos-dad.9  (bd sync research, P0)  ─┼─▶ cositos-dad.10 (dont sync design, P0)
                                         │        │
                                         │        ▼
                                         │   cositos-dad.1 (untrack .dont state, P0)
                                         │        │
                                         │        ▼
                                         │   cositos-dad.7 (clean tree)
                                         │        │
cositos-dad.2/.3/.4/.5/.6/.8 ───────────┴────────┴──▶ cositos-dad.11 (add remote + push)
                                                            │
                                          ┌─────────────────┼─────────────────┐
                                          ▼                 ▼                 ▼
                                  cositos-dad.12    cositos-dad.15/.16/.17/.18
                                  (verify bd sync)   (contribution-UX, split)
```

Run `bd graph cositos-dad` for the live, authoritative view—this document is
a snapshot of the reasoning, not the source of truth for status.

