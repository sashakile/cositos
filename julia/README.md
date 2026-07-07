# Cositos.jl — Julia backend

The Julia port of the cositos protocol core: builds/parses ipywidgets
widget-messaging-protocol v2.1.0 messages and does binary-buffer split/merge, with no
kernel/transport code. Reuses anywidget's `AnyModel`/`AnyView` frontend.

## Status
Protocol core certified against the shared golden fixtures in `../fixtures/`, plus a
kernel-agnostic `Widget` façade and two hosts: a **live IJulia** comm adapter
(`CositosIJuliaExt`, loads with `using IJulia`) and a **Pluto.jl** render/`@bind` host
(`CositosPlutoExt`). IJulia is Tier 1 (full two-way widget comm) — see `../probe/README.md`.

## Use

Protocol core (build/parse messages yourself):

```julia
using Cositos

data, buffers, metadata = build_comm_open(Dict("_esm" => esm, "value" => 0))
# send `comm_open` with (data, buffers, metadata) over your comm...

data, buffers = build_update(Dict("value" => 42))   # send as comm_msg
msg = parse_message(incoming_data)                    # Update | RequestState | Custom
```

Live widget in an IJulia (Julia Jupyter) kernel via the `Widget` façade + IJulia host:

```julia
using Cositos, IJulia

store = Dict{String,Any}("_esm" => esm, "value" => 0)
w = Widget(Cositos.ijulia_transport();
           get_state = () -> copy(store),
           set_state = (d) -> merge!(store, d))
open!(w)                 # sends comm_open over the kernel's iopub
store["value"] = 42; send_state!(w)   # push an update
display(mimebundle(w))   # render the widget view
```

Binary values are `Vector{UInt8}`. `buffer_paths` use 0-based array indices (wire
format); `put_buffers!` translates them back to Julia's 1-based indexing.

## Test

```bash
mise run julia-test      # or: julia --project=julia -e 'import Pkg; Pkg.test()'
```

The live IJulia round-trip is covered by an e2e test (launches a real IJulia kernel):

```bash
mise run e2e             # runs tests/test_e2e_julia.py (+ the Python e2e)
```
