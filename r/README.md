# Cositos (R)

Binding-free anywidget-style backend **protocol core** for an R Jupyter kernel (IRkernel)
— the R port of `src/cositos/` (Python reference), `julia/`, and `clojure/`.

Pure protocol logic (message builders, buffer split/merge, widget-state serialization)
with **no** kernel/transport code. Certified against the shared golden fixtures in
`../fixtures/*.json`.

```bash
Rscript test.R        # run the fixture-conformance suite
# or from the repo root:  mise run r-test
```

Requires `jsonlite` (JSON + base64), installed from CRAN:
`Rscript -e 'install.packages("jsonlite")'`.

## Conventions

- **State** is a named list (JSON object); **arrays** are unnamed lists.
- **Binary** values are R `raw` vectors; `buffer_paths` are lists of segments — string map
  keys and **0-based** integer list indices (the wire convention).
- Buffers are compared by **raw bytes**, never coerced-type equality.

## Status

Protocol core only. The `Transport` adapter over IRkernel's comm API + a live e2e round
trip is tracked separately (`cositos-ex2.6`) and gated on the kernel capability probe
(`cositos-ex2.1`).
