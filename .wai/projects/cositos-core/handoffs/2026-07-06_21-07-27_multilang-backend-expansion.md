---
date: 2026-07-06T21:07:27-0300
git_commit: 5b14b37
branch: main
directory: ~/cositos
issue: cositos-483.3/.6 (docs, done), cositos-d9n (Julia serialize, done), cositos-ex2 (language expansion epic)
status: handoff
---

# Handoff: docs reference/parity + Julia serialize + multi-language backend expansion

## Context

`cositos` is a **binding-free** anywidget-style backend core: define a widget frontend
(ESM) once, drive it from any Jupyter kernel language. It reuses anywidget's published
`AnyModel`/`AnyView` frontend (emits `_model_module="anywidget"`), so the core is pure
protocol logic (message builders, buffer split/merge, widget-state serialization) with a
thin per-kernel `Transport` seam. Cross-language correctness is pinned by **golden JSON
fixtures** (`fixtures/*.json`, `fixtures/widget-state.json`) every port certifies against.

This is a **tooling-evaluation sandbox**: `cositos` is built *using* the `charly-vibes`
CLIs (`wai` workflow, `dont`, `pretender` complexity, `ah`/espectacular specs). Charly-tool
friction goes in `TOOL_EVALUATION.md` + the published `../sandbox/charly-vibes-tools/`
report; **cositos-project** findings (like the kernel bugs below) go in beads/handoffs, not
the tool report.

## Current Status

### Completed this session (all committed to `main`, `mise run verify` green)
- [x] **`cositos-483.3`** — docs Reference (API by concern) + Specifications page (weaves
      OpenSpec specs via Quarto `{{< include >}}`) + Architecture explanation.
- [x] **`cositos-d9n`** — Julia widget-state serialization (`dump/load_document` + base64 +
      validation) in `julia/src/Cositos.jl`, certified vs `fixtures/widget-state.json`.
- [x] **`cositos-483.6`** — Python/Julia parity docs page: a panel-tabset showing both
      backends produce the identical document; Julia runs live at render via
      `examples/parity/dump.jl` with a byte-identity assertion (build fails on drift).
- [x] **Language expansion epic `cositos-ex2`** (design doc + 7 tickets):
  - [x] `ex2.2/3/4` — **Clojure, R, C# protocol cores**, all fixture-certified, each wired
        into `mise run verify` (`clojure-test`, `r-test`, `csharp-test`).
  - [x] `ex2.1` — **kernel capability probe** (`probe/kernel_probe.py`): classifies a kernel
        Tier 1/2/3 for widget comms. python3 certified Tier 1 (`tests/test_kernel_probe.py`).
- [x] `mise` **qa-* tasks** for manual QA of rendered paths (`qa`, `qa-export`, `qa-web`,
      `qa-docs`, `qa-notebook`).
- [x] Installed + verified-launching kernels: `python3`, `ir` (R), `.net-csharp`,
      `cositos-clj` (Clojure). Recipes in `probe/README.md`.

### Blocked / deferred (upstream reasons — NOT cositos defects)
- [ ] `ex2.6` **R transport** — IRkernel **1.3.2** (latest CRAN) has a broken kernel-initiated
      `comm$open()` (internal `send_response` arity error). Re-test: `mise run probe -- ir`.
- [ ] `ex2.7` **C# transport** — .NET Interactive doesn't answer `comm_info_request`; it uses
      its own bespoke protocol, not the standard ipywidgets comm surface.
- [ ] `ex2.5` **Clojure transport** — clojupyter answers `comm_info_request` (can receive) but
      exposes no user-facing API to *open* a comm from Clojure. Widgets need kernel-open.

## ⚠️ Top priority next: pre-existing P0/P1 bugs (static export is broken)

These were filed earlier and are the highest-priority open work — they also **contradict
docs I touched** (the static-export tutorials/README claim "works today"):
- **`cositos-mx7` (P0)** — static-HTML export omits anywidget view identity; the CDN
  html-manager fails to render. The `embed`/parity/export paths likely produce a JS error
  in-browser despite building green.
- **`cositos-d33` (P1)** — test gap: embed/static-export tests never assert view identity, so
  the broken rendering passes CI (this is why I didn't catch it).
- **`cositos-26l` (P1)** — widget linking / `IPY_MODEL_` reference composition unsupported —
  refs arrive as raw strings frontend-side.
- **`cositos-pvi` (P1)** — `mise run qa-notebook` launches JupyterLab without a widget
  frontend, so the counter renders as text, not interactive.
- **`cositos-3g5` (P2)** — docs/README "work today" claims are false where rendering errors.

**Do `mx7` + `d33` together** (fix + the missing assertion) — a real manual QA round
(`mise run qa-export`, open in a browser) will confirm. My session's docs assumed these
paths worked; verify before trusting them.

## Critical Files

1. `probe/kernel_probe.py` + `probe/README.md` — the capability probe, per-kernel probe
   programs (python3 ✓, ir present-but-blocked), install recipes, and the tier findings.
2. `clojure/`, `r/`, `csharp/` — the three new fixture-certified protocol cores (mirror
   `src/cositos/` + `julia/`). Each has a README and a `*-test` mise task in `verify`.
3. `src/cositos/embed.py` + `docs/tutorials/static-export.qmd` — the code + docs implicated
   by the P0 `mx7` (view-identity omission).
4. `fixtures/widget-state.json` — the cross-language golden contract (composed UI + float32).
5. `mise.toml` — task runner; language cores + qa-* + `probe` tasks live here.
6. `.wai/projects/cositos-core/designs/2026-07-06-design-expanding-the-cositos-backend-language-s.md`.

## Key Learnings

1. **The cositos thesis holds; the kernel comm ecosystem is the wall.** All 4 non-Python
   cores port trivially and certify. But only **python3** carries widgets end-to-end today:
   R (IRkernel bug), C# (.NET Interactive's non-standard protocol), Clojure (no comm-open API)
   are each blocked upstream. The **core/transport split** + **probe-first** design turned 3
   speculative ports into 3 cheap, documented, reproducible answers.
2. **`comm_info_request` is a fast language-agnostic capability signal** — no kernel-side code
   needed. NO reply (C#) ⇒ not the standard comm surface; YES (Clojure) ⇒ plumbing exists.
3. **clojupyter installs jar-free**: its standalone jar is a proxy-blocked GitHub release
   asset, but a hand-written kernelspec launching `clojupyter.kernel.core` via
   `clojure -Sdeps ...` from Clojars works (see `probe/README.md`).
4. **.NET kernelspec needs an `env` block** (absolute `dotnet`, `DOTNET_ROOT`, PATH incl.
   `~/.dotnet/tools`) or it dies before `kernel_info`.
5. **`examples/parity` must be instantiated with the mise-pinned Julia (1.11)**, not Homebrew
   1.12, or `mise run docs` fails in the render subprocess.
6. Per-language footguns are documented in each port's code/README (R NULL-in-list &
   mixed-type paths; C# zero-NuGet System.Text.Json; Clojure dependency-free test runner).

## Gotchas for the next session (from TOOL_EVALUATION.md)

- **Docs-only / non-`.py` commits fail lefthook** (F17) → use `git commit --no-verify`. Code
  commits with `.py` run hooks normally; run `mise run fmt` first.
- Stage commits **explicitly by path**; never `git add -A`. Beads data lives in Dolt, not git.
- **Quarto website render silently no-ops** (F18) if any input fails → keep `project.render:`
  scoped.
- `mise run verify` now runs **julia/clojure/r/csharp** cores too — all toolchains are
  installed (R 4.6.1, dotnet 10.0.301, Clojure CLI + Java 26). The probe test + e2e are opt-in.

## Next Steps (recommended order)

1. **`cositos-mx7` (P0) + `cositos-d33` (P1)** — fix static-export view-identity omission and
   add the missing assertion. Verify with a real browser QA round (`mise run qa-export`).
2. **`cositos-26l` (P1)** — `IPY_MODEL_` reference composition on the frontend.
3. **`cositos-pvi` (P1)** — qa-notebook widget frontend, or document the requirement.
4. Then choose a direction: the **widget-codegen (Option D)** epic (typed widget wrappers
   generated per language from one spec — discussed, not yet ticketed), or **publish
   `@cositos/front`** (the blocker for all non-Jupyter/web/Pluto rendering), or the
   **TypeScript host `cositos-eyl`** (Deno is Tier-2 and likely the best non-Python story).

## Related Links

- Design (this epic): `.wai/projects/cositos-core/designs/2026-07-06-design-expanding-the-cositos-backend-language-s.md`
- Probe + findings: `probe/README.md`
- Prior handoff: `.wai/projects/cositos-core/handoffs/2026-07-06_19-24-37_serialization-embed-quarto-docs.md`
- Resume: `bd ready`, `mise run verify`, `wai status`. Probe a kernel: `mise run probe -- <name>`.
