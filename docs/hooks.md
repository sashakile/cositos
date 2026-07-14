---
title: "Git hooks & local quality gates"
---


cositos enforces three gate families **on every commit/push** and in CI:

| Gate | Python (`src/`) | JS (`front/src/`) |
|---|---|---|
| **Lint / format** | `ruff check` + `ruff format --check` | (tsc covers style-adjacent issues) |
| **Typecheck** | `mypy --strict` | `tsc --checkJs --strict` |
| **Coverage** | `pytest --cov --cov-fail-under=95` | `c8` (lines ≥ 90, branches ≥ 85) |
| **Complexity** | `pretender check` | `pretender check` |
| **Spec contracts** | `ah check` | — |

- **pre-commit** (fast): lint, format, typecheck, complexity.
- **pre-push** (fuller): coverage (py + js), `ah check`.

Run everything manually at any time:

```bash
mise run verify       # lint + typecheck + coverage (py & js) + complexity + specs
mise tasks            # list all available tasks
lefthook run pre-commit --all-files
```

Gate commands live once in `mise.toml` as tasks; `lefthook.yml` invokes `mise run <task>`
so there is a single source of truth.

## How hook installation works here

Two tools want to own git hooks:

- **beads** sets `core.hooksPath = .beads/hooks` (for issue-jsonl sync + typos/vale).
- **lefthook** provides the quality-gate config in `lefthook.yml`.

Git hooks are **machine-local** (they never travel with a clone), so `lefthook.yml` is
the canonical, committed source of truth. On this machine the beads-managed
`pre-commit` and `pre-push` scripts **delegate** to `lefthook run <hook>` (guarded by
`command -v lefthook`), so both beads sync and the cositos gates run under beads'
`hooksPath`.

### Fresh-clone bootstrap

```bash
mise install                           # pinned node (uv + python come from system/uv)
mise run setup                         # uv sync + npm install
bd init                                # re-establishes .beads/hooks + hooksPath
# then append the two delegation lines (see .beads/hooks/{pre-commit,pre-push})
#   if command -v lefthook >/dev/null 2>&1; then lefthook run pre-commit || FAILED=1; fi
```

If you don't use beads, run `lefthook install --force` instead to let lefthook own the
hooks directly.

> **Internal reference:** See [`docs/_internal/bd-sync.md`](_internal/bd-sync.md) for
> details on how beads syncs issue data across machines using Dolt remotes, including
> setup commands, anti-patterns, and merge conflict resolution.
