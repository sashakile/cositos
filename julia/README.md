# Cositos.jl — Julia backend

The Julia port of the cositos protocol core: builds/parses ipywidgets
widget-messaging-protocol v2.1.0 messages and does binary-buffer split/merge, with no
kernel/transport code. Reuses anywidget's `AnyModel`/`AnyView` frontend.

## Status
Protocol core only (v0). Certified against the shared golden fixtures in `../fixtures/`.
A host adapter over IJulia's comm API (`jupyter.widget` target) is the next step.

## Use

```julia
using Cositos

data, buffers, metadata = build_comm_open(Dict("_esm" => esm, "value" => 0))
# send `comm_open` with (data, buffers, metadata) over your IJulia comm...

data, buffers = build_update(Dict("value" => 42))   # send as comm_msg
msg = parse_message(incoming_data)                    # Update | RequestState | Custom
```

Binary values are `Vector{UInt8}`. `buffer_paths` use 0-based array indices (wire
format); `put_buffers!` translates them back to Julia's 1-based indexing.

## Test

```bash
mise run julia-test      # or: julia --project=julia -e 'import Pkg; Pkg.test()'
```
