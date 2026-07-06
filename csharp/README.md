# Cositos (C#)

Binding-free anywidget-style backend **protocol core** for a .NET Jupyter kernel
(.NET Interactive) — the C# port of `src/cositos/` (Python reference), `julia/`,
`clojure/`, and `r/`.

Pure protocol logic (message builders, buffer split/merge, widget-state serialization)
with **no** kernel/transport code. Certified against the shared golden fixtures in
`../fixtures/*.json`.

```bash
dotnet run -c Release   # run the fixture-conformance suite (exit code gates CI)
# or from the repo root:  mise run csharp-test
```

**Zero NuGet dependencies** — `System.Text.Json` and `System.Convert` (base64) ship in the
shared framework, so no package restore is needed (robust behind restricted networks).

## Conventions

- JSON object = `Dictionary<string, object?>`; array = `List<object?>`; **binary** =
  `byte[]`; numbers = `long`/`double`.
- `buffer_paths` are `List<object?>` of segments — string map keys and **0-based** `long`
  list indices (the wire convention).
- Buffers are compared by **raw bytes** (`SequenceEqual`), never boxed-value equality.

## Status

Protocol core only. The `Transport` adapter over .NET Interactive's comm surface + a live
e2e round trip is tracked separately (`cositos-ex2.7`, highest-risk in the batch) and gated
on the kernel capability probe (`cositos-ex2.1`).
