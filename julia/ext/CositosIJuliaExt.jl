"""
CositosIJuliaExt — IJulia (Julia Jupyter kernel) host for cositos.

Loads automatically when `IJulia` is available. Provides an `IJuliaCommTransport` that
adapts IJulia's `CommManager.Comm` API to the kernel-agnostic cositos `Widget` façade —
the Julia analogue of Python's `cositos.jupyter.CommTransport`. Construct it with
[`Cositos.ijulia_transport`](@ref).

The comm is created lazily on the first `comm_open` send, carrying the initial state
exactly as the protocol requires (IJulia's `Comm` constructor emits `comm_open` on
construction). Frontend→kernel `comm_msg`s are echoed to the registered callback via the
comm's mutable `on_msg` field.
"""
module CositosIJuliaExt

using Cositos: Cositos
import IJulia
import IJulia.CommManager

"""IJulia comm transport: adapts `CommManager.Comm` to the cositos Transport contract."""
mutable struct IJuliaCommTransport
    comm::Union{CommManager.Comm,Nothing}
    pending::Union{Function,Nothing}
end
IJuliaCommTransport() = IJuliaCommTransport(nothing, nothing)

Cositos.ijulia_transport() = IJuliaCommTransport()
Cositos.supports_receive(::IJuliaCommTransport) = true
Cositos.comm_id(t::IJuliaCommTransport) = t.comm === nothing ? "" : String(t.comm.id)

function Cositos.transport_send(
    t::IJuliaCommTransport, msg_type, content; buffers=Any[], metadata=nothing
)
    if msg_type == "comm_open"
        _open!(t, content, buffers, metadata)
    elseif msg_type == "comm_msg"
        CommManager.send_comm(
            _require_comm(t), Dict{String,Any}(content), Dict{String,Any}(), _bufvec(buffers)
        )
    elseif msg_type == "comm_close"
        CommManager.close_comm(_require_comm(t))
    else
        error("Unknown comm message type: $(repr(msg_type))")
    end
    return nothing
end

function Cositos.transport_on_message(t::IJuliaCommTransport, callback)
    if t.comm === nothing
        t.pending = callback  # wired up on open
    else
        _bind!(t, callback)
    end
    return nothing
end

# -- internals -------------------------------------------------------------

# IJulia's Comm constructor sends comm_open (with data + metadata + buffers) as it is built.
function _open!(t::IJuliaCommTransport, content, buffers, metadata)
    md = metadata === nothing ? Dict{String,Any}() : Dict{String,Any}(metadata)
    t.comm = CommManager.Comm(
        Cositos.TARGET_NAME; data=Dict{String,Any}(content), metadata=md, buffers=_bufvec(buffers)
    )
    if t.pending !== nothing
        _bind!(t, t.pending)
        t.pending = nothing
    end
    return nothing
end

function _bind!(t::IJuliaCommTransport, callback)
    t.comm.on_msg = function (msg)
        data = get(msg.content, "data", Dict{String,Any}())
        callback(data, msg.buffers)
    end
    return nothing
end

function _require_comm(t::IJuliaCommTransport)
    t.comm === nothing && error("comm not opened; call open!() first")
    return t.comm
end

_bufvec(buffers) = Vector{UInt8}[Vector{UInt8}(b) for b in buffers]

end # module
