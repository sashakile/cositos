---
date: 2026-07-07
project: cositos-core
phase: research
---

# Session Handoff

> Note: this file replaced an earlier 2026-07-07 handoff (widget state-management
> research) due to a wai same-date filename collision; the prior one is preserved in git
> at commit 6d053fc.

## What Was Done

Executed the widget state-management epic (`cositos-ay3`) plus follow-on multi-language
planning. Commits are local (cositos has no git remote); the sandbox report was pushed.

1. **`cositos-ay3.5` (tooling-eval)** — re-verified this session's charly-vibes friction
   *live* and recorded F18,F21–F25 + an F2 correction in `TOOL_EVALUATION.md` and the
   published `../sandbox/charly-vibes-tools/dev-tooling-evaluation.md` (pushed `a893185`).
   Key correction: `dont`'s metacharacter guard has narrowed — `/`, `.`, `:` now accepted;
   only `;` rejected. The handoff's "dotted identifiers rejected" did **not** reproduce.
2. **`cositos-ay3.1` (state-discipline docs)** — `docs/explanation/state-discipline.qmd`:
   six rules distilled from `examples/benchmarks/` with A/B/C/D evidence + a topology→style
   table. Renders clean via `quarto render`.
3. **`cositos-ay3.3` (contrib.harvest)** — `cositos.contrib.harvest` / `harvest_html` over
   `ipywidgets.embed.embed_data` (its `manager_state` IS a cositos Document). Optional,
   lazy import, not in core `__init__`. 7 TDD tests.
4. **`cositos-ay3.2` (plot integration)** — `docs/tutorials/plot-integration.qmd` +
   runnable `examples/plots/build.py`. Verified live: Plotly 6 `FigureWidget` + Altair
   `JupyterChart` are anywidget-based (harvest+embed clean); bqplot uses `bqplot`/`bqscales`
   frontend modules (static-render caveat).
5. **Interactive-notebook-per-language planning** — created epic `cositos-059` + 6 children
   (Python ready; Julia = probe spike `059.3` + adapter `z76.6`; R/Clojure/C# blocked),
   wired deps (F14-safe), and enriched the blocked transport tickets (`ex2.5/6/7`, `z76.6`)
   with the empirical probe findings.
6. **Clojure blocker, precisely characterised** — introspected `clojupyter-0.4.332.jar`:
   comm plumbing exists, no widget layer; `send-comm-open!`/`send-comm-msg!` are `:private`;
   public `create`/`create-and-insert` need internal `jup`+`req-message`. Documented in
   `probe/README.md`, grounded a `dont` claim, refined tickets `059.5`/`ex2.5` with a
   concrete `current-context` spike.

## Key Decisions

- Harvest/plot ergonomics live in optional **`cositos.contrib`** (Python-only), never the
  fixture-certified core (verified `import cositos` doesn't pull ipywidgets).
- **"All 5 languages interactive" is not achievable now** — only Python is Tier 1; R/C#/
  Clojure are blocked upstream; Julia is the one winnable unknown (probe IJulia first).
- Left the concurrent process's in-flight mypy/pyproject work alone; only fixed my own
  `harvest.py` typing.

## Gotchas & Surprises

- **A concurrent process is active in this repo** — it committed the `pyproject.toml` mypy
  override (`135028b`) + test/refactor commits interleaved with mine.
- **The `mypy`/typecheck gate was already RED at session start** (`6d053fc`): unresolved
  `comm` imports in `src/cositos/jupyter.py` under `--extra dev`. Pre-existing, not mine.
- **F24 bit again:** my `uv pip install bqplot` (for ay3.2 verification) pulled `numpy`,
  whose 3.12-syntax stubs broke mypy at the 3.10 target. Fixed by `uv sync` (clean venv).
- **`wai close` clobbers a same-date handoff** with a blank template (this file) — new
  tooling-eval candidate; prior handoff safe in git.

## What Took Longer Than Expected

- Chasing the stray `pyproject.toml` change → discovered concurrent process + pre-existing
  red mypy gate + self-inflicted numpy pollution (several diagnostic rounds).

## Open Questions

- Pre-existing `comm` import failure in the mypy gate — fix separately, or is it the
  concurrent process's job?
- Julia IJulia widget-comm tier — the decisive unknown (`cositos-059.3`).

## Next Steps

1. **`cositos-059.3`** — install + probe IJulia (~10–30 min). If Tier 1, unblocks `z76.6`
   (IJulia adapter) + `059.2` (Julia notebook) → a second live language.
2. **`cositos-059.1`** — verify/polish the Python interactive notebook.
3. Remaining `cositos-ay3` P3s: `.4` (json_schema_to_document decision), `.6` (benchmark
   baseline defense + wall-clock timing).
4. Consider capturing the `wai close` same-date clobber as a TOOL_EVALUATION finding.

## Context

- Ready work (`bd ready`): `059.1`, `059.3` are the actionable multi-language items; the
  `ay3` P1/P2 children are all closed.
- All commits local (no cositos remote); sandbox report pushed (`a893185`).
