---
date: 2026-07-06
project: cositos-core
phase: research
git_commit: 8241fdd
branch: main
directory: ~/cositos
issue: mx7/d33/v38/ryh/0j7/pvi/3g5/e4j (static-export bug cluster) + y07/05i/cnq/915/qzk/und/6sp/dow/t3c (bug backlog)
status: handoff
---

# Session Handoff: static-export P0/P1 cluster + full bug-backlog cleanup

## Context (what cositos is)

`cositos` is a **binding-free** anywidget-style backend core: define a widget frontend
(ESM) once, drive it from any Jupyter-kernel language. It reuses anywidget's *published*
`AnyModel`/`AnyView` frontend (emits `_model_module="anywidget"`), so the core is pure
protocol logic — message builders, buffer split/merge, widget-state serialization — with a
thin per-kernel `Transport` seam. Cross-language correctness is pinned by **golden JSON
fixtures** (`fixtures/*.json`) every port certifies against. Ports: Python (reference),
Julia, R, C#, Clojure; plus `@cositos/front` (a standalone JS runtime for web/WASM/Pluto).

This is a **tooling-evaluation sandbox** (see `AGENTS.md`): cositos is built *using* the
`charly-vibes` CLIs (`wai`, `dont`, `pretender`, `ah`/espectacular). Tool friction →
`TOOL_EVALUATION.md`; cositos-project bugs → beads/handoffs.

## What Was Done

Resumed the prior "multilang-backend-expansion" handoff and cleared its entire flagged
P0/P1 list, then drained the whole open-bug backlog. **17 tickets closed across 14 commits
(`baf8f71`..`8241fdd`); `bd list --type bug --status open` is now empty. `mise run verify`
fully green (Python 97, Julia 54, R 28, C# 28, Clojure 29, front, specs 18). `ah check`
clean.** Nothing pushed.

### The static-export bug cluster (the "top priority" from the prior handoff)
- **mx7 (P0) + d33 (P1)** `baf8f71` — static HTML export omitted anywidget **view identity**
  (`_view_name`/`_view_module`/...), so the CDN html-manager errored `Failed to load view
  class "null"` and rendered nothing. Fixed by injecting view identity at the **embed
  layer** (`embed.with_view_identity`, reusing new `protocol.view_identity`) — NOT in the
  serialization codec — so `dump_document` stays a pure lossless codec and all 4 language
  ports keep certifying against the unchanged golden fixture. Added d33 tests + espectacular
  contract. Browser-verified.
- **v38 (P1, decision)** — recorded **option (b) DOCUMENT** for widget composition/linking:
  option (a) RESOLVE is architecturally impossible because static export uses anywidget's
  *published* `AnyModel` (no widget-reference traits) and cositos can't add traits without
  forking anywidget (breaks the binding-free thesis).
- **ryh** `9ededc7` — tested `examples/composition/` (a real `@jupyter-widgets/controls`
  `VBox` + `LayoutModel` at version `2.0.0`) proving anywidget children resolve; documented
  the `jslink`-doesn't-work-in-static-export caveat.
- **0j7** `28493e4` — corrected the false "cross-widget references resolve" docs claim.
- **pvi (P1)** `94d4a31` — `mise run qa-notebook` launched JupyterLab in a `--with` overlay
  env lacking the widget labextensions. Added a `notebook` extra; task now runs
  `--extra oracle --extra notebook`. Browser-verified interactive widget + click round-trip.
- **3g5** — re-verified (docs rebuilt) all "works today" claims now render; no source change.
- **e4j (P1)** `e31bc31` — Julia parity for mx7 done the **Option-B way**: added Julia
  `view_identity` + `with_view_identity` (embed layer); dump stays pure/fixture-certified.

### The bug backlog
- **y07 (P2)** `32063c5` — `put_buffers` silently corrupted state on `buffer_paths`/`buffers`
  length mismatch. Now raises (Python `zip(strict=True)`, Julia length check). Both ports.
- **05i (P2)** `9ebcf0b` — `parse_message` raised on unknown comm methods (broke forward-
  compat vs ipywidgets). Now returns a benign `Ignored` sentinel; `Widget._handle` no-ops.
  Updated protocol spec + espectacular contract (reject→ignore).
- **cnq (P3)** `c285a89` — `_as_bytes` fell back to `tobytes()` for non-contiguous
  memoryviews (strided numpy views) instead of `TypeError`.
- **915 (P3)** `4038a2e` — `remove_buffers` now detects cycles (ancestor-id chain) and caps
  depth with a clear `ValueError` instead of `RecursionError`; DAGs not misreported.
- **qzk (P3)** `5b4bf99` — new opt-in `check_references(doc)` catches dangling
  `IPY_MODEL_<id>` refs (cycles/diamonds valid). Exported from the package.
- **und (P3)** `f5be06a` — `open()` idempotent; `send_state`/`send_custom` before `open()`
  raise a clear error.
- **6sp (P3)** `8ddba25` — corrected the web-demo counter comment (no doubling reducer).
- **dow (P3)** `d9d1eb4` — `parse_message` ignore-unknown parity across Julia/R/C#/Clojure
  (all gained an `Ignored`-style result; tests flipped from throw→ignore).
- **t3c (P1)** `8241fdd` — `load_document` was **destructive**: `load_model` aliased
  `record['state']` and `put_buffers` merged raw bytes into it, so a later `json.dumps`/
  `embed_html` on the same Document raised "bytes not JSON serializable". Now deep-copies
  state before merging buffers (Python + Julia). Regression tests per port.

## Key Decisions

1. **View identity belongs in the embed/static-render layer, not `dump_document`** (v38 /
   mx7). This is the load-bearing architectural call of the session: it keeps the
   serialization core a pure lossless codec that certifies byte-for-byte against the shared
   golden fixture across all 5 ports, mirroring how the *live* path injects identity in
   `build_comm_open` (not in stored state). It changed how e4j (Julia) and the ticket's
   literal acceptance criteria were interpreted — the literal "inject in dump" would have
   broken cross-language fixture parity.
2. **Composition = option (b) DOCUMENT** (v38): plain anywidget widgets don't resolve
   references; use a `@jupyter-widgets/controls` container. `jslink` doesn't survive static
   export. Recorded, not worked around.
3. **Fix cross-language ports for parity when the bug is identical** (y07, dow, t3c covered
   all affected ports), but **split into follow-up tickets when a ticket was scoped to one
   language** (e4j from mx7, dow from 05i) rather than silently widening scope.

## Gotchas & Surprises

- **A concurrent session is running in this repo.** These untracked paths are NOT mine —
  do not commit them under this handoff: `examples/benchmarks/`, and
  `.wai/.../handoffs/2026-07-06_21-49-34_tooling-audit-enforcement-gates.md` (commit
  `7d7faba` `chore(dont)` and issue `cositos-83x`, `F19/F20` belong to that session).
- **Docs-only / non-`.py` commits fail the lefthook** (known F17) → use
  `git commit --no-verify`. Code commits with `.py` run hooks fine (`mise run fmt` first).
- **`mise run fmt` only formats `src tests`** — not `examples/` or ports; run
  `ruff format` on example `.py` manually.
- **espectacular slugs**: an apostrophe in a scenario title becomes `-s-` in the contract
  filename (`each-model-s-state-...`). Match the slug or `ah check` reports orphan-toml.
- **`qa-notebook` env**: JupyterLab MUST share the env that owns the widget labextensions
  (`--extra oracle --extra notebook`), never a `--with` overlay.
- **`915` depth cap**: `remove_buffers` temporarily raises `sys.setrecursionlimit` so the
  `_MAX_DEPTH=500` `ValueError` trips *before* the interpreter's `RecursionError`.

## What Took Longer Than Expected

- **mx7** — the fix itself was small, but choosing *where* to inject view identity required
  discovering that the golden fixture certifies 4 other ports (so touching `dump_document`
  breaks them). That drove the whole Option-B layering decision. Verified in a real browser
  (http.server + Chrome) because structural tests miss render failures — exactly the d33 gap.
- **pvi** — needed a live JupyterLab launch + Run-All + click to confirm the labextension
  discovery fix (the bug is invisible to headless nbconvert).

## Open Questions

- Should the Option-B `with_view_identity` also be added to the R/C#/Clojure ports? Only
  Julia got it (e4j) because only Python+Julia have any static-export surface today. Filed
  nothing — revisit if/when those ports grow an embed path.
- Push policy: all 14 commits are **local only**; no push authorization was given.

## Next Steps

1. **Push** the 14 commits once authorized (branch `main`).
2. Pick a direction (all P2 epics, no bugs left):
   - **`cositos-eyl`** — TypeScript backend host + fixture conformance (Deno is Tier-2; the
     best non-Python story per the prior probe).
   - **publish `@cositos/front`** — the blocker for all non-Jupyter web/WASM/Pluto rendering.
   - **`cositos-5q7`** — `hosts.md` channel guide; **`cositos-54t`** — WASM host + demo.
   - widget-codegen epic (typed per-language wrappers from one spec) — discussed, not ticketed.
3. Low-hanging docs: `cositos-483.4` (Observable/Deno example), `cositos-483.5` (README/llm.txt
   wiring + `wai way` findings).

## Critical Files (touched this session)
- `src/cositos/embed.py` — `with_view_identity` (mx7 core); `src/cositos/protocol.py` —
  `model_identity`/`view_identity`/`Ignored`; `src/cositos/serialize.py` — pure `load_model`
  (t3c), `check_references` (qzk), non-contiguous `_as_bytes` (cnq); `src/cositos/buffers.py`
  — cycle/depth guard + strict `put_buffers` (915/y07); `src/cositos/model.py` — lifecycle (und).
- `julia/src/Cositos.jl` — `with_view_identity` (e4j), pure `load_model` (t3c), strict
  `put_buffers!` (y07), `Ignored` (dow).
- `examples/composition/build.py` (ryh); `mise.toml`+`pyproject.toml` (pvi).
- Ports: `r/core.R`, `csharp/Core.cs`, `clojure/src/cositos/core.clj` (dow).

## Related Links
- Prior handoff: `.wai/projects/cositos-core/handoffs/2026-07-06_21-07-27_multilang-backend-expansion.md`
- Resume: `bd ready`, `mise run verify`, `wai status`.

## Context

### git_status

```
?? .wai/projects/cositos-core/handoffs/2026-07-06-session-end.md
?? .wai/projects/cositos-core/handoffs/2026-07-06_21-49-34_tooling-audit-enforcement-gates.md
?? examples/benchmarks/
```

### open_issues

```
○ cositos-483 ● P2 [epic] Quarto documentation site (polyglot, runnable widget examples)
├── ○ cositos-483.4 ● P3 docs: Observable JS (Deno) backend-less widget example
└── ○ cositos-483.5 ● P3 docs: wire site into README/llm.txt + fix wai way docs findings
○ cositos-5q7 ● P2 docs: hosts.md (Jupyter/web/wasm/Pluto channel guide)
○ cositos-83x ● P2 Gate on dont: add 'dont verify' to verify + pre-push once dont supports external evidence (F1)
○ cositos-ex2 ● P2 [epic] expand backend language set (batch 1: C#, Clojure, R)
○ cositos-eyl ● P2 TypeScript backend host + fixture conformance
○ cositos-z76 ● P2 [epic] Display & static-HTML export (Voila/Quarto/JupyterBook/myBinder)
○ cositos-54t ● P3 WASM host channel + demo

--------------------------------------------------------------------------------
Total: 9 issues (9 open, 0 in progress)

Status: ○ open  ◐ in_progress  ● blocked  ✓ closed  ❄ deferred
```
