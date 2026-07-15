# Changelog

## [0.2.0] — 2026-07-15

### Added
- **Lifecycle reducer + shell (Python):** `WidgetShell` class, pure `reduce()` function, effect/event types (`Send`, `Listen`, `ApplyState`, `InvokeCustom`, `Error`, `Open`, `SendState`, `SendCustom`, `Inbound`, `Close`, `CommIdAssigned`), `Phase` enum, `TransportCapabilities` struct. Replaces imperative `Widget` internals with delegation to `WidgetShell`. 31 fixture-based tests.
- **Lifecycle reducer + shell (Julia):** Full port of lifecycle types, `reduce()`, and `WidgetShell` in `Cositos.jl`. Deprecated `Widget` wrapper preserves backward compat. 20 lifecycle fixture certification tests.
- **Lifecycle reducer + shell (C#):** `Lifecycle.Reduce` static method, `WidgetShell` class, all effect/event types in `Core.cs`. 29 lifecycle fixture certification tests.
- **Lifecycle reducer + shell (R):** `reduce()` function, effect/event makers, phase sentinels in `core.R`. 29 lifecycle fixture certification tests.
- **Buffer-split edge cases:** Cycle detection and depth capping for Julia, C#, Clojure, R (Python already had it). Code-based test cases in every language.
- **Transport capability flags:** `supports_request_state`, `supports_custom`, `supports_buffers` added to `Transport` protocol, `CommTransport`, Julia `WidgetShell` constructor, and Julia `IJuliaCommTransport`.
- **Clojure transport docstring:** Explicit capability flag breakdown (supports_receive=YES, supports_request_state=NO, supports_custom=NO, supports_buffers=NO).
- **Documentation:** `fixtures/README.md` covering protocol, lifecycle, and controls catalog fixtures. `docs/porting.md` Step 5 (Widget Lifecycle) with transition table and shell pattern. `docs/reference/api-cheatsheet.qmd` lifecycle reducer symbol table.
- **Specs:** New `openspec/specs/lifecycle/` and `openspec/specs/lifecycle-shell/` capabilities. Updated `openspec/specs/protocol/` with cycle-detection and depth-cap requirements.

### Fixed
- Julia `send_state!`: identity re-merge on full send now mirrors Python's behavior (cositos-k43 parity).
- Cross-repo documentation links converted to GitHub-absolute URLs to prevent 404s on the deployed site.
- Clojure depth-capping test: reduced nesting depth from 2001 to 600 to prevent JVM stack overflow before the guard fires.

### Changed
- `Widget` class (Python): deprecated in favor of `WidgetShell`. Public API unchanged — existing code continues to work.
- `Widget` struct (Julia): deprecated wrapper around `WidgetShell`. Public API unchanged.
- `Transport` protocol: extended with `supports_request_state`, `supports_custom`, `supports_buffers` optional fields.

[0.1.3]: https://github.com/sashakile/cositos/releases/tag/v0.1.3
