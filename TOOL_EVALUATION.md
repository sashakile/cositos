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
it penalises well-written claims. Same likely applies to `:` and `/` in prose.

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

