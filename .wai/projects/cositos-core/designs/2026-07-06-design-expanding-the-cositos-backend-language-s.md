# Design: expanding the cositos backend language set (batch 1: C#, Clojure, R)

## Goal

Prove the cositos thesis — *one widget frontend, driven from any Jupyter kernel language*
— beyond the Python reference and the Julia port, by adding backend cores for **C#,
Clojure, and R** (batch 1; other languages follow later). Each new language must certify
against the shared golden fixtures exactly as Julia does, with no change to the core's
binding-free philosophy.

## Background (what already exists)

- **Python** is the reference implementation (`src/cositos/`), and the source of the golden
  fixtures (`fixtures/*.json`, `fixtures/widget-state.json`).
- **Julia** (`julia/src/Cositos.jl`) is a full protocol-core port: message builders, buffer
  split/merge, and (as of `cositos-d9n`) widget-state serialization — all fixture-certified.
  Its *hosting* (IJulia comm adapter, Pluto) is deferred pending a live kernel and the
  unpublished `@cositos/front` bundle.
- The porting contract is documented in `docs/porting.md`: a port implements (1) the pure
  protocol core, (2) a `Transport` adapter, then (3) certifies against the fixtures.

## The central design decision: split every port into core vs. transport

A port has two halves with radically different risk profiles. **Batch 1 treats them as
separate deliverables.**

| Half | What it is | Needs a kernel? | Risk |
|---|---|---|---|
| **Protocol core** | message builders + buffer split/merge + serialization (~150–200 LOC) | **No** — pure logic, tested in the language's own runner against the fixtures | Low / mechanical |
| **Transport + e2e** | adapter over the kernel's comm API + a live round-trip test | **Yes** — and the kernel must be comm-capable | High / gated |

This mirrors the precedent already set by Julia (shipped core-only, hosting deferred). It
lets batch 1 make certifiable progress on all three cores even where a kernel is missing,
uncertain, or blocked by the environment.

## The gating factor for transports: comm capability, not language

Widgets *are* Jupyter comms. Every kernel falls into one of three tiers, and this — not
the language — determines the widget experience:

| Tier | Kernel can… | Experience | Known / suspected members |
|---|---|---|---|
| **1. Bidirectional** | open + send + **receive** | full two-way widgets | ipykernel ✓, IJulia ✓ (proven); R (IRkernel) *likely*; xeus-* *likely* |
| **2. Broadcast-only** | open + send, no reply routing | one-way (`supports_receive=false`) | Deno (handled) |
| **3. No comm** | cannot open comms | widgets impossible without a kernel patch | many community kernels; **Clojure/clojupyter unverified** |

Tier membership for batch-1 kernels is **unverified** and must be established empirically
(see the capability probe) before investing in a transport.

## Per-language landscape (to verify, not trust)

- **R (IRkernel):** toolchain via Homebrew (`r`); IRkernel installs from CRAN (not GitHub
  release assets, so proxy-permitted). Comm manager has existed for years → *likely Tier 1*,
  completeness unverified.
- **C# (.NET Interactive):** toolchain via Homebrew (`dotnet`); kernel via `dotnet tool`.
  Not a vanilla Jupyter kernel — it layers its own kernel protocol, so how cleanly the
  ipywidgets comm maps is the **highest-uncertainty** item in the batch.
- **Clojure (clojupyter):** toolchain already present (Clojure CLI + Java). Kernel install
  needed; **comm support is the open question** — may be Tier 3, which would make the
  transport infeasible without upstream changes (core still ships and certifies).

## The kernel-capability probe (shared, build once)

Before any transport work, generalize the existing `e2e` harness (which drives a real
kernel via `jupyter-client`) into a **capability probe**: given an installed kernel name,
attempt `comm_open` + a state round-trip and classify the kernel Tier 1/2/3. One small
artifact answers "can language X support widgets?" empirically in seconds, and sequences
the transport work by confirmed tier instead of guesswork.

## Certification approach (unchanged, per language)

Each core reproduces `fixtures/*.json` byte-for-byte (modulo comm id and buffer encoding)
in the language's native test runner, exactly as `julia/test/runtests.jl` does:
`build_comm_open` / `build_update` / `build_custom` / `parse_message` / buffer split/merge,
plus `dump/load_document` against `fixtures/widget-state.json`. Buffers compare by **raw
bytes**. The fixtures are the language-neutral contract; no core is "done" until green.

## Sequencing (environment-driven)

1. **Clojure core** — the only batch-1 language whose toolchain is present today; start
   immediately (TDD against fixtures, no installs, no kernel).
2. **R core** — after `brew install r`.
3. **C# core** — after `brew install dotnet`.
4. **Capability probe** — build once; classify R/C#/Clojure kernels.
5. **Transports** — implement only for confirmed Tier 1/2 kernels; defer the rest (as Julia
   hosting is deferred). Some batch-1 transports may not land, and that is acceptable.

## Relationship to the widget-codegen decision (Option D)

Separately, the project chose **Option D**: generate typed, idiomatic widget wrappers per
language from a single declarative spec. Each new backend language is therefore *also* a
future D codegen target. The two efforts are complementary but independent — D should be
proven on Python+Julia first, then each batch-1 language becomes a target. Batch 1 here is
scoped to **protocol cores + (gated) transports only**; widget wrappers are out of scope.

## Non-goals (batch 1)

- Shipping typed widget wrappers (that is the D codegen effort).
- Guaranteeing a transport for every batch-1 language — transports are gated by verified
  comm capability and may defer.
- Publishing `@cositos/front` — still the blocker for any non-Jupyter (web/Pluto) rendering;
  unchanged by this work.
- Host-idiomatic ergonomics (observer autodetection, hot-reload) — optional, later.

## Risks

- **Proxy blocks GitHub release assets** — kernel installs sourced from GitHub releases may
  fail; prefer Homebrew/CRAN/`dotnet tool`/language package managers.
- **Clojure kernel may be Tier 3** — the core still ships, but the transport could be
  infeasible without upstream clojupyter comm support.
- **.NET Interactive comm mapping** — its bespoke kernel-protocol layer may not surface the
  ipywidgets comm cleanly; verify with the probe before committing to the transport.
- **Toolchain drift** — three new language toolchains add CI/verify surface; keep each core
  behind its own `mise` task and out of the default `verify` unless the toolchain is present
  (mirrors how `julia-test` / `docs` are handled).

