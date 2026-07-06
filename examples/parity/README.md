# Python / Julia parity example

Emits the **same** widget-state `Document` from the Julia port that
`cositos.dump_document` emits in Python — the runnable core behind the
[Python / Julia parity](../../docs/tutorials/polyglot-parity.qmd) docs page.

```bash
# One-time (resolve deps into this project; uses the mise-pinned Julia):
mise exec -- julia --project=examples/parity -e 'import Pkg; Pkg.instantiate()'

# Print the serialized Document as canonical JSON:
mise exec -- julia --project=examples/parity examples/parity/dump.jl
```

The docs page runs `dump.jl` at render time and asserts its output equals Python's, so the
two backends can never silently drift. Parity is also certified independently: both
implementations reproduce the shared golden fixture `fixtures/widget-state.json` in their
own test suites.

This project `dev`s the local `../../julia` package and adds `JSON` (used only to print
the document — `Cositos.jl` itself, like `cositos.serialize`, has no JSON dependency).
