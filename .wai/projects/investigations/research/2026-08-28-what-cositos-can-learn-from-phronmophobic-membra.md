# What cositos can learn from phronmophobic/membrane

**Date:** 2026-07-14
**Source:** https://github.com/phronmophobic/membrane (Clojure UI library, v0.14.4-beta)
**Kind:** advisory investigation — no code changes proposed yet

## Context

Investigated membrane as an architectural reference. Membrane is a Clojure UI
library built on the same philosophy cositos claims: a platform-agnostic data
model, a pure-functional component framework, and thin per-platform backends
(macOS/Linux/WebGL; experimental terminal, skija, JavaFX, iOS). Its stated
porting contract: *"to run on a platform, the only requirements are (1) drawing
implementations for primitives, (2) an event loop that forwards events."*

## Findings

### 1. Architecture is a proof-of-concept for cositos' core bet
Membrane demonstrates the exact pattern: small canonical core + minimal
per-platform seam. Its crisp two-requirement porting contract is the model for
how `docs/extending/porting.md` frames the ~150-line port. Its terminal backend
shows graceful degradation for primitives a platform can't render — analogous
to cositos' `supports_receive = false` for one-way hosts.

### 2. Independent validation for the effects-returning reducer
`membrane.component` event handlers are pure functions returning effects (or
`nil`) rather than performing them — same shape as cositos' lifecycle reducer
returning effect lists to the shell. Independent convergence from a mature
Clojure UI library is good evidence the pattern generalizes. Membrane's state
management (kept outside the pure layer) may inform edge cases in
`src/cositos/lifecycle.py` (focus, layout pass).

### 3. Concrete opportunity: a MembraneChannel for Clojure hosts (most actionable)
Cositos already has `LocalChannel` / `PlutoChannel` seams and a Tier-1 Clojure
backend via Clay. Since membrane renders to desktop, terminal, and WebGL from
pure Clojure data, a **`MembraneChannel`** could render cositos widget state as
membrane UI values and feed membrane events back through the channel — live
widgets in a native window or terminal, outside Jupyter, zero new JavaScript.
`membrane.term` (terminal todo-mvc) is a working template.

### 4. Docs pattern
Membrane pairs code with "background and theory" essays. A short "why a pure
reducer, and why Elm/Redux/membrane all converged on it" section in
`architecture.qmd` citing membrane would strengthen the porting pitch.

## Bottom line

No code to lift — different problem domain — but membrane is the closest
architectural sibling in the Clojure ecosystem, a possible frontend target for
a non-Jupyter channel, and a good citation for the reducer design.

## Next step (optional)

File a beads issue for the MembraneChannel idea if pursued.

