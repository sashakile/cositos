# Contributing to cositos

Thank you for considering contributing to cositos! This document outlines the
project conventions and workflows.

## Getting started

1. Fork the repository and clone your fork.
2. Run `mise install` to install pinned tool versions.
3. Run `mise run setup` to install Python and JS dependencies.
4. Run `mise run verify` to confirm everything passes on a clean checkout.

## Development workflow

cositos follows a **test-driven development** workflow using the `bd` (beads)
issue tracker for durable task tracking:

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

For every ticket: implement using TDD (red → green → refactor), run the full quality
gate suite listed below and fix all findings, then commit.

### Quality gates

Run `mise run verify` before every commit — it runs linting, typechecking,
coverage, complexity analysis, and spec-contract checks:

| Gate | Python (`src/`) | JS (`front/src/`) |
|---|---|---|
| **Lint / format** | `ruff check` + `ruff format --check` | (tsc covers style-adjacent issues) |
| **Typecheck** | `mypy --strict` | `tsc --checkJs --strict` |
| **Coverage** | `pytest --cov --cov-fail-under=95` | `c8` (lines ≥ 90, branches ≥ 85) |
| **Complexity** | `pretender check` | `pretender check` |
| **Spec contracts** | `ah check` | — |

### Commit conventions

- Make atomic, revertible commits — stage explicitly by path, never `git add -A`.
- Keep structural changes (formatting, refactoring) separate from behavioural changes.

### Documentation

cositos uses a Quarto-based documentation site under `docs/`. Build and preview:

```bash
mise run docs           # build docs/_site/
mise run qa-docs        # build + open it
mise run docs-preview   # live-reload preview while editing
```

## Reporting issues

- **Bug reports:** Open a GitHub issue with a minimal reproduction (expected vs. actual
  behaviour, cositos version, kernel language and version).
- **Feature requests:** Describe what you want to accomplish and why existing mechanisms
  don't cover it.

## Code of conduct

Please note that this project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md).
By participating you agree to uphold its terms.