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

Protocol core only. The `Transport` adapter over clojupyter's comm API + a live e2e round
trip is tracked separately (`cositos-ex2.5`) and gated on the kernel capability probe
(`cositos-ex2.1`) — clojupyter's comm support is not yet verified.
