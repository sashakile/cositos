# Git hooks & local quality gates

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
just verify          # lint + typecheck + coverage (py & js) + complexity + specs
lefthook run pre-commit --all-files
```

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
uv sync --extra dev --extra oracle     # Python deps
(cd front && npm install)              # JS deps
bd init                                # re-establishes .beads/hooks + hooksPath
# then append the two delegation lines (see .beads/hooks/{pre-commit,pre-push})
#   if command -v lefthook >/dev/null 2>&1; then lefthook run pre-commit || FAILED=1; fi
```

If you don't use beads, run `lefthook install --force` instead to let lefthook own the
hooks directly.
