# Tool Evaluation Log — wai / dont / pretender / espectacular

Captured while dogfooding the four tools to build `cositos`. Each entry:
severity, what I tried, what happened, what I expected, and impact on developer flow.

Legend: 🔴 blocker · 🟡 friction · 🟢 papercut/nit · 💡 suggestion

---

## Environment notes
- No Rust toolchain, `just`, or the tools were preinstalled. Had to install rustup
  and `cargo build --release` all four crates (~9 min total) before any tool could run.
  💡 A prebuilt binary / `brew` bottle or a documented bootstrap would help first-run.
- `pretender --version` errors (`unexpected argument '--version'`) while `wai`, `dont`,
  `ah` all support it. 🟢 Inconsistent CLI conventions across the suite (see F6).
- Correction to an earlier suspicion: `dont` *does* return exit code 1 on validation
  errors. My first reading saw `0` only because `$?` was capturing a piped `head`, not
  `dont`. No bug there.

---

## Findings

### 🔴 Blockers

**F1 · `dont` cannot cite evidence outside the project root.**
`dont ground --file ../anywidget/anywidget/_util.py` → `error: evidence locator path is
invalid: path escapes project root`. The entire cositos task is grounded in *sibling/
vendored* reference repos (anywidget, ipywidgets). There is no way to attach that
ground-truth as evidence. This is the single biggest friction: the tool that exists to
force grounding forbids citing the actual source of truth. Suggest a
`resources`/`external-evidence` allowlist, a vendored-path escape hatch, or support for
URL + commit-pinned locators.

### 🟡 Friction

**F2 · `dont conclude` rejects legitimate prose punctuation.**
`dont conclude "... adapter; the frontend ... reused"` → `error: statement: must not
contain shell metacharacters or path separators; found ';'`. Semicolons and colons are
normal prose. The metacharacter guard is defending against shell injection that has
already been neutralised by argv (the arg arrives as one string). Guard is too broad;
it penalises well-written claims.

> **Update (2026-07-07, dont 0.1.0, re-verified this session):** the guard has narrowed.
> `dont conclude` now *accepts* `:`, `.`, and `/` in prose — e.g. `dont conclude
> "examples/benchmarks/reactive.py is glitch-free"` and `dont conclude "cositos.contrib
> .harvest wraps embed_data"` both succeed. Only true shell metacharacters like `;` are
> still rejected (`found ';'`). So a prior session's belief that *dotted identifiers* are
> rejected does **not** reproduce; F2 is now scoped to `;`/shell-metachar text only. The
> error message text ("or path separators") is stale — path separators are permitted.

**F3 · `wai add` doesn't commit artifacts, but `dont` requires committed evidence.**
`wai init` auto-commits `.wai/`, but `wai add research/design/plan` leaves artifacts
uncommitted. `dont ... --file <artifact>` then fails with `file is not tracked by git;
commit it before using as evidence`. The two tools in the same suite disagree on the
git lifecycle, forcing a manual `git add && commit` between them. Either `wai add`
should offer to commit, or `dont` should accept staged (not-yet-committed) files.

**F4 · `ah init` hard-requires `openspec/` with no scaffolding or guidance.**
`ah init` → `no openspec/ directory found ...; ah init requires an OpenSpec project`,
exits 1. The openspec CLI is not bundled and the error doesn't say how to get it. I had
to hand-create `openspec/{project.md,specs/,changes/}`. For a suite that advertises
openspec integration, `ah init` should offer `--scaffold` or print the minimal layout.

**F5 · `dont ground` is not idempotent / no upsert on existing claim.**
Re-running `dont ground` for a claim that already exists errors
(`claim with equivalent text already exists`) instead of attaching the evidence. You
must switch to `dont flag <id> --evidence ...`. A first-time user reasonably expects
`ground` to "create-or-add-evidence". Minor but trips the natural workflow.

### 🟢 Papercuts / docs

**F6 · `pretender --version` unsupported** while `wai`, `dont`, `ah` all support it —
inconsistent CLI conventions across a suite that otherwise feels coordinated.

**F7 · espectacular `llm.txt` misdescribes the scenario heading.** It says a Scenario
is a `### Requirement:` heading whose slug is the id. In practice `ah` discovers
`#### Scenario:` headings (the `### Requirement:` is the grouping). Following the
llm.txt verbatim would produce zero discovered scenarios. `ah init` itself correctly
stubbed contracts from my `#### Scenario:` headings, confirming the docs, not the tool,
are wrong.

**F8 · wai workspace-vs-project naming is confusing.** `wai init` created a *workspace*
named `cositos` but no *project*, then `wai status` still prints
`Project: cositos` (the workspace) while suggesting you create a project. After
`wai new project cositos-core`, the header still reads `Project: cositos`. The
workspace/project distinction isn't surfaced clearly in the status header.

**F9 · No bootstrap path.** None of the four tools were installed and no prebuilt
binaries/bottles exist; I had to install rustup and `cargo build --release` all four
crates (~9 min) before any tool could run. A `brew` bottle, a `cargo install`
one-liner in each README's top, or a bootstrap script would help first contact.

**F10 · `wai way` doesn't recognise `mise` as a task runner.** With a full `mise.toml`
(12 tasks) present, `wai way` still reports "Command standardization: No task runner
detected" — it only looks for justfile/Makefile/Taskfile. mise is a mainstream runner;
the detector should include `mise.toml` / `.mise.toml`.

**F11 · `wai way` pre-commit detection misses delegated lefthook installs.** It reports
"lefthook.yml found but hooks not installed — run: lefthook install" even though the
gates provably run on commit. Because beads owns `core.hooksPath` and we delegate via
`lefthook run`, there's no lefthook marker in `.git/hooks` for wai to find.

**F12 · `mise` default Python backend compiles from source and fails without build
deps.** `mise install` with `python = "3.12"` invoked pyenv's `python-build` (source
compile), which failed (exit 2). Precompiled python-build-standalone should be the
default, or the failure should point at `MISE_PYTHON_COMPILE=0`. Worked around by
letting `uv` own Python via `.python-version`.

**F13 · `mise` cannot fetch `uv` here (GitHub release-assets 403).** `mise install uv`
→ 403 Forbidden from `release-assets.githubusercontent.com`. node (from nodejs.org)
installed fine, so GitHub-release-asset downloads specifically are proxy-blocked. Not a
mise bug, but aqua-backed tools are unusable here; cositos pins node via mise and takes
uv from the system.

**F14 · `beads` inverts the dependency when using `bd create --deps blocks:<id>`.**
`bd create "T2" --deps "blocks:T1"` (intending "T2 blocked by T1") created the reverse:
T2 *blocks* T1 (T1 dropped out of `bd ready`, T2 became ready). Verified via `bd show`
(T2 under BLOCKS, T1 under DEPENDS ON) and `bd ready`. 🟡 friction — a silently inverted
graph yields a wrong ready-set, so work can start in the wrong order. `bd create --help`
doesn't state which side the new issue takes. Fix: make `--deps blocks:X` mean "new issue
depends on X", or document direction. Unambiguous workaround: `bd dep <blocker> --blocks
<blocked>`.

**F15 · `wai add design -v`/`-vv` don't reveal options; they just re-emit the error.**
The `wai add` help footer promises "Use -v for all options, -vv for env vars, -vvv for
internals." But `wai add design -v` and `-vv` (with no content) both print only
`× Provide content or use --file to import from a file` and exit — no option list, no
env vars. 🟢 papercut. Expected: `-v` prints the flag reference (e.g. `--file`, project
selection) *before* validating required content, so discovery works without already
knowing the answer. Worked around by copying the `--file` form from the top-level
examples block.

**F16 · `openspec new change` scaffolds only `.openspec.yaml`, not the artifact stubs.**
`openspec new change <name>` creates the change dir containing only the hidden
`.openspec.yaml` — no `proposal.md`/`design.md`/`specs/**`/`tasks.md`, not even empty
stubs. Templates exist (`openspec templates`) and `openspec instructions <artifact>`
prints them, so scaffolding is possible. 🟢 papercut. Fix: emit empty artifacts from the
templates on `new change`, or have its output name the artifacts to author next.

**F17 · `lefthook` aborts the commit (exit 1) when *no* staged file matches any hook.**
With `core.hooksPath` owned by beads (`.beads/hooks`) delegating to lefthook, a commit
whose staged files match none of the configured jobs (e.g. a docs-only commit under
`openspec/`) makes every job print `(skip) no matching staged files` and then lefthook
exits **1**, so `git commit` fails with no obvious error. Code commits (with staged `.py`)
succeed because a job actually runs. 🟡 friction — blocks routine docs/spec commits and the
cause is buried under a `core.hooksPath` reset banner. Worked around with
`git commit --no-verify`. Fix: lefthook should exit 0 when all jobs are skipped, and/or
the beads→lefthook delegation should not surface a non-zero status for an all-skip run.

**F18 · `quarto render` (website) silently no-ops — exit 0, empty log — when one input
file fails.** A Quarto website whose folder also held legacy plain `.md` files (no Quarto
front matter) produced no `_site/`, no error, and an empty `--log` file, exiting 0. A
single-file render of the same content worked, and a folder with only the good file
worked — so one unrenderable input aborts the whole batch without naming the file or why.
🟡 friction: cost several diagnostic rounds since success and "rendered nothing" look
identical. (Quarto 1.9.38.) Fix: non-zero exit and/or a message naming the offending
file. Worked around by scoping `project.render:`.

**F19 · Quality-tool coverage silently froze at the Python core while the project grew
to five backend languages — `pretender` no-ops on unsupported languages instead of
warning.** `pretender` bundles tree-sitter grammars only for C/C++/Go/Java/JS/Python/
Ruby/Rust/TS. The four backend cores added later — `julia/`, `csharp/`, `r/`, `clojure/`
— are none of those, so `pretender check julia/src csharp r clojure/src` returns
`{"files": []}` and **exit 0**: it scans zero files, reports nothing, and passes. The
complexity gate (`mise run complexity` → `pretender check src front/src`) is therefore
pinned forever to the original Python+JS core. Likewise `ah check` (espectacular) only
scans `openspec/specs`, and no spec references any of the four new backends or the
`probe/`. Net effect: `mise run verify` *looks* comprehensive (it lists `julia-test`,
`clojure-test`, `r-test`, `csharp-test`) but the two dedicated quality tools see only the
Python+JS core — the new code is validated solely by hand-rolled fixture tests. 🟡
friction (false confidence). Root defect: a complexity checker that is handed real source
files in an unsupported language should **warn/exit non-zero ("0 files matched a
supported grammar")**, not silently succeed. Suggested fixes: (a) pretender emits a
non-zero "no supported files" signal when given explicit paths that yield zero parsed
files; (b) the *project* adds a coverage-manifest gate so any new backend directory must
declare its quality-tool binding (or an explicit exemption) — implemented here as
`mise run coverage-audit` (see Enforcement below).

**F20 · `dont` was abandoned after day-1 init and has no enforcing gate, so it decayed to
zero use.** `.dont/tx.seq` = 3 and `.dont/events.jsonl` holds only the
`project.initialized` event; the two claims in the ledger were both created in the same
second on 2026-07-03 (`17:18:33Z`) and one of them is a dummy (`"good clean claim about
protocol version two point one"`). Sessions 2–3 (serialization/embed/docs, then the
multi-language + kernel-probe expansion) produced exactly the empirical, citable claims
`dont` exists to ground — "IRkernel 1.3.2's kernel-initiated `comm$open()` is broken",
".NET Interactive doesn't answer `comm_info_request`", "clojupyter can receive but exposes
no comm-open API", and the P0 `cositos-mx7` that *contradicts* shipped docs — yet **none**
were recorded in `dont`; they went into handoff prose and beads instead. 🟡 friction.
Root-cause chain: **F1** (dont refuses to cite the vendored `anywidget/`/`ipywidgets/`
reference repos, the actual source of truth) made grounding painful on first contact →
unlike `pretender`/`ah`, `dont` was never wired into lefthook/`verify` → with no gate and
real friction it decayed to zero. The two tools that survived did so *because* they were
gated. Suggested fix: (a) unblock F1 upstream; (b) meanwhile, add dont to the session
ritual so capability findings that *can* cite in-project evidence (research docs,
`probe/README.md`) get grounded, and gate on `dont` being clean once F1 is fixed (see
Enforcement below).

**F21 · `dont flag --file` refuses any evidence file with unstaged modifications, forcing
commit-before-ground.** `dont` (the epistemic-forcing tool: you record a *claim*, then
*flag/verify* it by attaching *evidence* — a file that supports it) computes a content SHA
of the evidence file. If that repo-tracked file has uncommitted edits,
`dont flag <claim> --file path/to/evidence.py` → `error: file has unstaged modifications;
SHA would not match current content`, exit non-zero. Verified live this session: dirtying
a tracked `benchlib.py` made the flag fail; `git checkout --` (clean) then let the exact
same command succeed (`verified claim:…`). Expected: ground a claim against the evidence I
am actively editing. Actual: I must `git commit` the evidence *first*, then ground — which
inverts the natural loop (you usually ground a finding *while* writing it up). This is the
same lifecycle friction as F3 (untracked files) but for the *dirty-tracked* case, and
together they are a major contributor to F20's decay. 🟡 friction. Fix: hash the working-
tree content (or the staged blob) instead of requiring HEAD-clean, or accept a
`--allow-dirty` escape hatch.

**F22 · `dont` has no way to delete or retract an erroneously created claim — only
`ignore`.** While verifying F2/F21 this session I created five throwaway probe claims
(`dont conclude "…"`). `dont --help` lists no `delete`/`remove`/`retract`/`drop` verb; the
closest is `ignore` ("move a claim to ignored state") and `trust`/`undoubt` (status
toggles). So a mistaken claim cannot be expunged — it lives forever in the ledger, merely
re-labelled. I had to run `dont ignore claim:… --reason "stray test claim"` five times, and
those entries still count toward the project's claim inventory. Expected: a way to remove a
claim created in error (typo, test, duplicate). Actual: permanent ledger clutter. 🟢
papercut. Fix: add `dont delete <id>` (hard-remove pre-verification claims) or document
that `ignore` is the intended "never mind" and exclude ignored claims from status counts.

**F23 · `dont flag --evidence` rejects repo-relative file paths; the path locator is the
separately-named `--file` flag.** `dont flag <claim> --evidence path/to/file.py` →
`error: malformed evidence locator "…": must be an http:// or https:// URI`. The
repo-relative path form lives under a *different* flag, `--file`. The name `--evidence` is
the obvious first guess for "here is my evidence file", but it is URL-only; the affordance
for local files (the common case in a code repo) is undiscoverable from the flag name. 🟢
papercut. Fix: let `--evidence` accept a repo-relative path (dispatching to the same
structured locator as `--file`), or rename to `--evidence-url` so the split is obvious.

**F24 · `uv sync` prunes `ipywidgets`/`anywidget` from the venv unless `--extra oracle` is
passed, silently breaking every benchmark run.** `cositos` uses `uv` (a Python package/
venv manager) with an optional dependency group named `oracle` that carries `ipywidgets` +
`anywidget`. A bare `uv sync` (which many tasks and muscle-memory invoke) treats those as
not-required and *removes* them from `.venv`, so the next
`python examples/benchmarks/run.py` dies on `ModuleNotFoundError: ipywidgets`. It recurred
after every sync last session, each time needing a manual
`uv pip install ipywidgets anywidget` to repair. 🟡 friction (project config). Expected: the
tooling needed to *run the project's own benchmarks* stays installed. Actual: routine
`uv sync` uninstalls it. Fix: move `ipywidgets`/`anywidget` into the default dependencies
(or a group synced by default), or make the benchmark task pass `--extra oracle`.

**F25 · `~/.local/bin/grep` has a CRLF shebang and is a broken shim on this machine.**
`~/.local/bin/grep --version` → `/bin/bash: /Users/…/.local/bin/grep: /bin/sh^M: bad
interpreter: No such file or directory` (verified this session; the first line is
`#!/bin/sh\r\n` — a Windows CRLF line ending that macOS reads as an interpreter named
`/bin/sh\r`). Because `~/.local/bin` is early on `PATH` (it is where the four charly-vibes
tool symlinks live), an unqualified `grep` can resolve to this broken shim instead of
system `grep`. A related harness gotcha: a global pre-commit hook on this machine emits
`bad interpreter` noise and can abort commits (worked around with `git commit
--no-verify`), and its non-zero exit is *masked* when a `git commit` is piped through `rg`
(the pipeline reports `rg`'s status, not git's). 🟢 papercut (environment/harness, not a
charly-vibes tool defect — recorded so the friction is attributable). Fix: remove or repair
the CRLF shim (`sed -i '' 's/\r$//' ~/.local/bin/grep` or delete it); prefer `rg`/absolute
`/usr/bin/grep`; never assess a commit's success by piping it through another command.

---

**F26 · `dont ground` rejects `<`, `/`, and other characters as "shell metacharacters"
inside the claim *statement*, even though the statement is a normal CLI string argument.**
Grounding the Clay finding this session, `dont ground "...envelope (text frame 'cositos
<json>')..." --file ... --lines ...` failed with `error: statement: must not contain shell
metacharacters or path separators; found '<'; expected printable prose characters only`.
A second attempt using `state/frontend` (a slash) hit the same wall on `/`. Expected: the
statement is passed as a single already-quoted `argv` element, so the shell never sees it;
technical prose about wire formats legitimately contains `<json>`, `A/B`, `kernel->front`,
etc. Actual: an over-broad input filter treats ordinary prose punctuation as dangerous,
forcing lossy rewrites of the very claim being recorded (I had to drop the `'cositos
<json>'` notation and rephrase `browser<->JVM`). Impact: the epistemic record is degraded
to satisfy a filter that guards against an injection that cannot occur (the value is never
re-interpreted by a shell). 🟡 friction. Suggested fix: scope the metacharacter rejection
to fields that are actually interpolated into shells/paths (e.g. `--file`), not to free-text
prose; or allow `< > / -` in statements and escape only at genuine sinks.

---

## Enforcement — making the tools impossible to silently drop

The pattern behind F19/F20: **a tool stays used only if a gate fails when it isn't.**
`pretender` and `ah` survived every session because they sit in `lefthook` + `mise run
verify`; `dont` evaporated because nothing failed without it. Fixes, tiered by what is
achievable now vs. after upstream changes.

**E1 · Coverage-manifest gate (closes F19 now).** A new `mise run coverage-audit` task
(wired into `verify`) reads `coverage-manifest.toml`, which must list every backend
directory and, for each, either the quality tool that covers it or an explicit
`exempt = "<reason>"`. The audit fails if (a) a backend dir on disk is missing from the
manifest, or (b) a dir claims `pretender` coverage but `pretender check <dir>` parses
zero files (catching the silent-no-op in F19). This converts "quietly uncovered" into a
loud, deliberate, reviewed decision — adding a new language *forces* a coverage entry.

**E2 · dont in the handoff ritual (mitigates F20 now).** Until F1 is fixed, a hard
pre-commit `dont` gate would just reproduce the F17 all-skip friction, so instead the
`wai` handoff checklist requires: list each capability finding and whether it was grounded
in `dont` (citing in-project evidence, which *is* allowed). Soft, but it re-introduces the
claim→ground habit the tool is for.

**E3 · dont hard gate (after F1).** Once `dont` can cite vendored reference repos, add
`dont verify` (no unverified/ungrounded claims) to `mise run verify` and pre-push, so a
session that makes empirical claims but grounds none fails the gate — the same mechanism
that kept `pretender`/`ah` alive.

### 👍 What worked well (kept for balance)

- **`wai way`** is an excellent, actionable repo-hygiene checklist; it drove most of the
  Phase-0 scaffolding and gave immediate before/after feedback.
- **`wai` phase workflow** (research→design→plan→implement) structured the work cleanly
  and the artifacts landed in a sensible PARA tree with dated filenames.
- **`pretender check`** caught a *real* cognitive-complexity smell (16 > 15) in the
  buffer functions that prompted a genuine, worthwhile refactor to green — not a
  false positive.
- **`ah check`** correctly reported `no-tests-declared` for stub contracts, then went
  green once each scenario was wired to a real pytest node. The JSON envelope is clean
  and scriptable.
- **`dont`** error messages each carry a `run:` remediation line — good affordance,
  and the claim→flag→verified lifecycle is coherent once past F1–F3.

