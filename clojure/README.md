# Cositos (Clojure)

Binding-free anywidget-style backend **protocol core** for a Clojure Jupyter kernel
(clojupyter) — the Clojure port of `src/cositos/` (Python reference) and `julia/`.

It is pure protocol logic (message builders, buffer split/merge, widget-state
serialization) with **no** kernel/transport code — a host supplies that. It is certified
against the shared golden fixtures in `../fixtures/*.json`.

```bash
clojure -M:test        # run the fixture-conformance test suite
# or from the repo root:  mise run clojure-test
```

## Conventions

- **State** is a map with string keys; **lists** are vectors.
- **Binary** values are Java byte arrays (`bytes?`); `buffer_paths` use string map keys and
  **0-based** integer list indices (the wire convention).
- Buffers are compared by **raw bytes**, never typed-array identity.

## Status

Protocol core (`src/`): fixture-certified, no kernel dependency.

Two live-widget transports exist, dev-only (not part of the certified core, since both
need a live kernel/host to run at all):

- **`cositos.clay`** (`src/cositos/clay.clj`) + `dev/cositos/clay_demo.clj` /
  `clay_notebook.clj` -- Clay's public full-duplex websocket. **Recommended**: no internal
  APIs, full buffer/`custom`-message support. See `docs/hosts.md`.
- **`cositos.clojupyter-transport`** (`dev/cositos/clojupyter_transport.clj`) -- a live
  comm round trip against clojupyter itself, confirmed in `cositos-059.9` via
  `clojupyter.state/current-context`, an internal, version-coupled implementation detail
  (not a public/upstream API). Supports the `update` (state-sync) round trip only: no
  binary buffers, no `custom` messages. Notebook: `examples/notebooks/clojure_counter.ipynb`;
  live-kernel test: `tests/test_e2e_clojure.py`.
