---
date: 2026-07-06T19:24:37-0300
git_commit: a8105ac
branch: main
directory: ~/cositos
issue: cositos-483 (docs), cositos-zi8 (serialization, done), cositos-z76 (hosting)
status: handoff
---

# Handoff: serialization + static export + Quarto docs

## Context

`cositos` is a binding-free anywidget-style backend core (define a widget frontend once,
drive it from any Jupyter kernel language). This is a **tooling-evaluation sandbox**: we
build `cositos` *using* the `charly-vibes` CLIs (`wai` workflow, `dont`, `pretender`
complexity, `ah`/espectacular specs) and log every friction point (see `TOOL_EVALUATION.md`
locally and `../sandbox/charly-vibes-tools/dev-tooling-evaluation.md` published).

This session shipped three things: **widget-state serialization** (save/restore + compose),
**static-HTML export + a live-display shim**, and a **Quarto documentation site** (Phases
1–2). All committed to `main`, all gates green.

## Current Status

### Completed (all committed, `mise run verify` green)
- [x] **Serialization epic `cositos-zi8`** (6 tasks) — `src/cositos/serialize.py`:
      `dump/load_model`, `dump/load_document`, base64 buffer codec, `model_id` validation,
      golden `fixtures/widget-state.json`, Hypothesis PBT. OpenSpec `serialization`
      archived to `openspec/specs/serialization/spec.md`. 100% cov.
- [x] **Display shim `cositos-z76.1`** — `Widget._repr_mimebundle_` + `open()` now syncs
      `model_id` from the transport's real comm id (fixed a latent wrong-id display bug).
- [x] **Static export `cositos-z76.2`** — `src/cositos/embed.py`: `embed_html` / `embed_snippet`
      / `write_html`; OpenSpec `embed` archived. `embed_snippet` added in docs Phase 1.
- [x] **Hosting recipes** — `z76.3` Voila/Binder (`examples/binder/`), `z76.4`
      Quarto/JupyterBook + verified nbconvert mechanism (`examples/static-export/`,
      opt-in test `tests/test_static_export.py`).
- [x] **Docs Phase 1 `cositos-483.1`** — Quarto site scaffolded (`docs/_quarto.yml`,
      `docs/index.qmd`); a widget renders **statically** in the built site. `mise run docs`.
- [x] **Docs Phase 2 `cositos-483.2`** — migrated 4 legacy pages + 2 runnable tutorials
      (`docs/tutorials/save-restore.qmd`, `static-export.qmd`).
- [x] Tooling findings F14–F18 logged locally and published to the sandbox report.

### Deferred (blocked on external prerequisites)
- [ ] `cositos-z76.5/.6/.7` — Julia/Pluto **hosting**: IJulia comm adapter needs a live
      IJulia kernel to verify; Pluto demo needs `@cositos/front` served (unpublished).

### Planned (ready — see Next Steps)
- [ ] `cositos-483.3` reference + explanation pages (P2, ready)
- [ ] `cositos-483.4` Observable/Deno backend-less widget example (P3, ready)
- [ ] `cositos-483.5` wire docs into README/llm.txt + fix `wai way` docs findings (P3)
- [ ] `cositos-d9n` **Julia serialization port** (P2, ready) — blocks `483.6`
- [ ] `cositos-483.6` Python/Julia parity tabs (blocked by `d9n`)

## Critical Files

1. `src/cositos/serialize.py` — the persistence core (types + codec + dump/load).
2. `src/cositos/embed.py` — static-HTML export; `embed_snippet` is the inline primitive.
3. `src/cositos/model.py:_repr_mimebundle_` + `open()` — display + comm-id sync.
4. `fixtures/widget-state.json` — the cross-language golden contract (composed UI + float32 buffer).
5. `docs/_quarto.yml` — site config; `project.render:` is **scoped** to migrated pages (see F18).
6. `.espectacular/serialization/*.toml`, `.espectacular/embed/*.toml` — spec→test contracts (17 pass).

## Key Learnings

1. **Reconstruction needs no `Message` sum type.** Option A (host rebuilds objects, calls
   `Widget.open()`) replays no message list — so serialization stayed additive/non-breaking.
2. **Buffers must compare by raw bytes** (`memoryview(x).cast('B')`), not memoryview equality
   — a float32 view ≠ plain-bytes view with identical bytes (`ipywidgets/.../widget.py:147`).
3. **`dump_model` must NOT inject `_model_*` into `state`** or the round-trip law breaks;
   anywidget identity lives in the Record top-level (`model_name`/`model_module`).
4. **Static widget embedding = `metadata.widgets["...widget-state+json"]`** — the shared
   mechanism for nbconvert/Quarto/JupyterBook. cositos widgets don't auto-register with an
   ipywidgets manager, so the state must be injected explicitly (verified via nbconvert).
5. **Quarto is the docs system** — it natively runs Python/Julia/Deno (verified `quarto check`),
   fitting the polyglot library; installed at `/Applications/quarto/bin/quarto` (symlinked to
   `~/.local/bin/quarto`). Build with `mise run docs` (sets `QUARTO_PYTHON=.venv/bin/python`).
6. **The `@cositos/front` unpublished-bundle blocker only affects the web/Pluto path** — the
   Jupyter/Quarto/nbconvert path renders via anywidget's `AnyModel` from the CDN (no front needed).

## Open Questions

- [ ] Full Python/Julia parity docs need `Cositos.jl` to gain serialization (`cositos-d9n`) —
      do that before `483.6`.
- [ ] Should `mise run docs` join `mise run verify`? Kept separate (like `e2e`) since Quarto
      isn't always present.

## Next Steps

1. `cositos-483.3` — reference (API + weave `openspec/specs/*`) + explanation (architecture:
   "the Document is the virtual DOM", transport seam). Verifiable via `mise run docs`.
2. `cositos-483.4` — an `ojs`/Deno cell rendering a backend-less widget (polyglot, no kernel).
3. `cositos-d9n` — port serialization to `Cositos.jl`, certify vs `fixtures/widget-state.json`.
4. `cositos-483.5` — README/llm.txt link + `wai way` docs findings.

## Gotchas for the next session (from TOOL_EVALUATION.md)

- **Commits with only docs/non-`.py` staged fail** (lefthook exits 1 when all hooks skip, F17)
  → use `git commit --no-verify` for docs-only commits. Code commits run hooks normally.
- **`ruff format` is stricter than `ruff check`** → run `mise run fmt` (or `ruff format`) before
  committing `.py`, or the `format` hook aborts the commit.
- **Quarto website render silently no-ops** (exit 0, empty log) if any input file fails (F18)
  → keep `project.render:` scoped; legacy `docs/*.md` now have front matter.
- Stage commits **explicitly by path** (never `git add -A`); beads data lives in Dolt, not git.

## Artifacts

New (this session): `src/cositos/serialize.py`, `src/cositos/embed.py`, `fixtures/widget-state.json`,
`tests/test_serialize.py`, `tests/test_embed.py`, `tests/test_static_export.py`,
`docs/_quarto.yml`, `docs/index.qmd`, `docs/tutorials/{save-restore,static-export}.qmd`,
`examples/{web,notebooks,static-export,binder}/*`, `openspec/specs/{serialization,embed}/spec.md`,
`.espectacular/{serialization,embed}/*.toml`, `.wai/projects/cositos-core/designs/2026-07-06-*.md`.

Modified: `src/cositos/{model,__init__}.py`, `pyproject.toml` (extras: export, docs), `mise.toml`
(docs tasks), `docs/{widgets,porting,pluto,hooks}.md` (front matter), `TOOL_EVALUATION.md`.

## Related Links

- Designs: `.wai/projects/cositos-core/designs/2026-07-06-design-serializable-widgets-*.md`
  and `...-design-notebooks-static-html-export-and-integ.md`
- Specs: `openspec/specs/{protocol,serialization,embed}/spec.md`
- Published tooling report: `../sandbox/charly-vibes-tools/dev-tooling-evaluation.md`
- Resume context: run `bd ready` and `mise run verify`; `wai status` for the workflow trail.
