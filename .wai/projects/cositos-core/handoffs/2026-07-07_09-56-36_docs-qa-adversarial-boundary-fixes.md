---
date: 2026-07-07T09:56:36-0300
git_commit: 1ce6d6a
branch: main
issues: cositos-dzt (closed), cositos-qhx (closed)
status: handoff
---

# Handoff: docs QA (browser-driven) + adversarial boundary fixes

## Context

Resumed after the tooling-audit/enforcement session. This session was **QA on cositos
itself** (not the charly-vibes tools): a round of QA against the *live* Quarto
documentation site, then an adversarial "try to break things" pass on the public API. Two
real defects surfaced and were fixed TDD-style. All widgets/claims were exercised in a
**real browser**, not just asserted in prose.

## Current Status

### Completed (committed)

- [x] **Docs QA — 3 doc defects fixed** — commit `605d5b5`.
  - `docs/reference/index.qmd`: `parse_message` was documented as returning **3** typed
    events and "rejecting" unknown methods. The code (cositos-05i) returns a **4th type
    `Ignored` and never raises** — a self-contradiction with the protocol spec woven into
    the *same site*. Fixed signature + prose.
  - Same file: the union type's `\|` escapes rendered as **literal backslashes** inside
    the markdown-table inline-code span (pandoc doesn't process escapes inside code
    spans). Re-authored as one code span per type so the `\|` sits *outside* backticks →
    renders clean `Update | RequestState | Custom | Ignored`.
  - `docs/porting.md`: broken path `.wai/projects/cositos-core/design/` → `designs/`;
    also documented `parse_message`'s forward-compatible ignore behaviour.
- [x] **Browser verification** (served `docs/_site` + repo root, drove Chrome):
  - Home + static-export widgets render statically **and increment on click** (3→5).
  - `examples/composition/vbox.html` (controls `VBox`) **resolves both anywidget child
    references** ("child: one / two") — the hardest composition claim.
  - `examples/web/index.html` (`LocalChannel`, no kernel) counter works (0→3).
  - `tutorials/polyglot-parity.html`: Python and Julia tabs are **byte-identical**
    (Julia runs at render time).
  - Specs page `{{< include >}}` directives resolved; `#protocol/#serialization/#embed`
    anchors present; site-wide link/anchor scan clean.
  - **XSS claim holds:** injected `</script><script>window.__PWNED=1</script>` + an
    `onerror` img into widget state → `<` escaped to `\u003c`, nothing executed, title
    unchanged.
- [x] **`cositos-dzt` (P1) fixed** — commit `7fbf8af`. `parse_message(data)` crashed with
  `AttributeError: '…' object has no attribute 'get'` on non-dict wire data (`None`, str,
  list, int, bytes). **Reachable**: `Widget._handle(data,…)` → `parse_message(data)`,
  where `data` is the raw `comm_msg` `data` field from the frontend. Defeated the exact
  forward-compat goal of cositos-05i. Fix: `isinstance` guard returns `Ignored()`; param
  type widened to `Any`; parametrized regression test. Closed.
- [x] **`cositos-qhx` (P2) fixed** — commit `1ce6d6a`. `load_document` did
  `doc["state"].items()` with **no envelope validation** → bare `KeyError: 'state'` on a
  malformed doc, and **silently accepted any `version_major`** (returned `[]` on empty
  state). Asymmetric with `dump_document`'s strict id validation. Fix: validate at the
  boundary — clear `ValueError` on missing/non-mapping `state` and unsupported
  `version_major` (higher `version_minor` still accepted); 4 regression tests; porting
  guide updated. Closed.

### Adversarial claims that HELD (couldn't break)

- Lossless round-trip: empty `b""`, `bytearray`, nested buffers in lists/dicts, unicode
  dict keys, non-contiguous memoryviews — all byte-exact.
- `dump_document` guards: empty id, duplicate id, cyclic state → clear `ValueError`s.
- Weird model ids (`"a b/c\n"`), unknown `views=[…]` selection, empty-document embed —
  all graceful.
- XSS/`</script>` breakout — no execution (see above).

## Critical Files

1. `src/cositos/protocol.py` — `parse_message` non-dict guard (dzt).
2. `src/cositos/serialize.py` — `load_document` envelope validation (qhx).
3. `tests/test_protocol.py` — `test_parse_non_dict_is_ignored` (parametrized).
4. `tests/test_serialize.py` — `test_load_document_rejects_*` / `_accepts_supported_version`.
5. `docs/reference/index.qmd`, `docs/porting.md` — the doc fixes.

## Key Learnings

1. **The inbound/deserialization boundary trusted its input** while the out-path
   (`dump_document`, buffer split) validates aggressively — the asymmetry is exactly where
   both bugs lived. Parse-don't-validate applied at both boundaries now.
2. **Browser QA catches what asserts can't**: the reference-table `\|` backslash bug only
   showed in rendered HTML; the widget-interaction and composition claims only prove out by
   clicking in a real browser.
3. **pandoc does not process `\` escapes inside inline-code spans** — put table-cell pipe
   separators *outside* backticks.

## Gotchas carried forward

- **Concurrent session active on `main`**: benchmark commits (`b72aefb`, `96089bb`,
  `cd68a1f`, …) landed *interleaved* with mine — HEAD is now past my commits. `git pull
  --rebase` before any push; stage explicitly by path.
- The lefthook **`format`** hook is `ruff format --check` (check-only) → it *aborts* the
  commit if a staged file isn't already formatted (it does not auto-fix). Run
  `.venv/bin/ruff format src tests` before committing. Hit this once on qhx.
- `~/.local/bin/grep` has a CRLF shebang (`bad interpreter`) — filter it from git-hook
  output; use `rg`.
- Rendering docs needs the uv env: `mise run docs` (sets `QUARTO_PYTHON` to `.venv`).

## Next Steps

1. `bd ready` — remaining scope is pre-existing epics (more backends: C#/Clojure/R/TS;
   Quarto site wiring `cositos-483.*`; static-export epic `cositos-z76`; WASM host
   `cositos-54t`; `cositos-83x` = the blocked dont-gate E3).
2. No new defects left open from this session — both found bugs are fixed and closed.
3. Full suite green: **108 passed, 1 skipped**; gates green (ruff, mypy --strict,
   pretender, `ah check` 18/18, coverage-audit).

## Related Links

- Prior handoff: `.wai/projects/cositos-core/handoffs/2026-07-06_21-49-34_tooling-audit-enforcement-gates.md`
- Resume: `bd ready`, `mise run verify`, `mise run docs`, `wai status`.
