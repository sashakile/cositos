"""
    Cositos

Binding-free anywidget-style backend core for the Julia Jupyter kernel (IJulia).

This module is the Julia port of the cositos protocol core: it builds and parses
ipywidgets widget-messaging-protocol v2.1.0 messages and performs binary-buffer
split/merge, with **no** kernel/transport code (a host supplies that). It is certified
against the shared golden fixtures in `../fixtures/*.json`.

Binary values are `Vector{UInt8}`. Note the wire protocol uses **0-based** indices in
`buffer_paths` for array positions; this module emits and consumes them accordingly,
translating to/from Julia's 1-based indexing internally.
"""
module Cositos

using Base64: base64encode, base64decode

export PROTOCOL_VERSION, ANYWIDGET_MODULE_VERSION,
    build_comm_open, build_update, build_custom, mimebundle,
    parse_message, Update, RequestState, Custom, Ignored,
    remove_buffers, put_buffers!,
    dump_model, load_model, dump_document, load_document,
    view_identity, with_view_identity,
    WidgetShell, Widget, open!, close!, send_state!, send_custom!,
    Phase, UNOPENED, OPEN, CLOSED,
    TransportCapabilities,
    Send, Listen, ApplyState, InvokeCustom, Error,
    Open, SendState, SendCustom, Inbound, Close, CommIdAssigned,
    reduce,
    supports_receive, supports_request_state, supports_custom, supports_buffers,
    comm_id, transport_send, transport_on_message, ijulia_transport,
    PlutoWidget, local_front_runtime_url,
    int_slider, dropdown, vbox, hbox

const PROTOCOL_VERSION_MAJOR = 2
const PROTOCOL_VERSION_MINOR = 1
const PROTOCOL_VERSION = "$(PROTOCOL_VERSION_MAJOR).$(PROTOCOL_VERSION_MINOR).0"

#: Widget State JSON schema version (distinct from the protocol version 2.1.0).
const STATE_VERSION_MAJOR = 2
const STATE_VERSION_MINOR = 0

const TARGET_NAME = "jupyter.widget"
const WIDGET_VIEW_MIMETYPE = "application/vnd.jupyter.widget-view+json"

"Default anywidget frontend semver range this backend targets."
const ANYWIDGET_MODULE_VERSION = "~0.11.*"

isbinary(x) = x isa Vector{UInt8}
iscontainer(x) = (x isa AbstractDict || x isa AbstractVector) && !isbinary(x)

function model_identity(version::AbstractString)
    return Dict{String,Any}(
        "_model_module" => "anywidget",
        "_model_name" => "AnyModel",
        "_model_module_version" => version,
    )
end

"""
    view_identity(version) -> Dict

anywidget's immutable *view* fields — the identity the html-manager needs to pick a view
class. In schema v2 these live inside each model's `state`.
"""
function view_identity(version::AbstractString)
    return Dict{String,Any}(
        "_view_module" => "anywidget",
        "_view_name" => "AnyView",
        "_view_module_version" => version,
        "_view_count" => nothing,
    )
end

_immutable_fields(version::AbstractString) =
    merge(model_identity(version), view_identity(version))

# ---- lifecycle types (effect/event vocabulary, phase, capabilities) ----

"""
    Phase

The three phases of a widget's lifecycle: `UNOPENED`, `OPEN`, `CLOSED`.
"""
@enum Phase begin
    UNOPENED
    OPEN
    CLOSED
end

"""
    TransportCapabilities

Declares which event kinds the transport can carry. The reducer uses these flags
to decide which effects to produce.
"""
Base.@kwdef struct TransportCapabilities
    supports_receive::Bool = true
    supports_request_state::Bool = true
    supports_custom::Bool = true
    supports_buffers::Bool = true
end

# ---- Effect types ----

"Send a Jupyter comm message to the frontend."
struct Send
    msg_type::String
    data::Dict{String,Any}
    buffers::Vector{Any}
    metadata::Union{Dict{String,Any},Nothing}
end
Send(msg_type::AbstractString, data; buffers=Any[], metadata=nothing) =
    Send(String(msg_type), Dict{String,Any}(data), collect(buffers), metadata)

"Register an inbound message callback on the transport."
struct Listen end

"Apply an inbound state dict to the host object."
struct ApplyState
    state::Dict{String,Any}
end

"Invoke the host's custom message handler. Buffers are raw `Vector{UInt8}`."
struct InvokeCustom
    content::Any
    buffers::Vector{Any}
end
InvokeCustom(content; buffers=Any[]) = InvokeCustom(content, collect(Vector{UInt8}, buffers))

"An error effect — the shell shall raise an error in response."
struct Error
    message::String
end
Error(message::AbstractString) = Error(String(message))

# ---- Event types ----

"User/host wants to open the comm."
struct Open end

"User/host wants to send an update with optional include filter."
struct SendState
    include::Union{Set{String},Nothing}
end
SendState(; include=nothing) = SendState(include === nothing ? nothing : Set{String}(include))

"User/host wants to send a custom message."
struct SendCustom
    content::Any
    buffers::Vector{Any}
end
SendCustom(content; buffers=Any[]) = SendCustom(content, collect(buffers))

"An inbound message arrived from the transport, with buffers already merged."
struct Inbound
    message::Dict{String,Any}
    buffers::Vector{Any}
end
Inbound(message; buffers=Any[]) = Inbound(Dict{String,Any}(message), collect(buffers))

"User/host wants to close the comm."
struct Close end

"The transport assigned a comm id after a comm_open send."
struct CommIdAssigned
    id::String
end
CommIdAssigned(id::AbstractString) = CommIdAssigned(String(id))

# ---- lifecycle reducer ----

"""
    reduce(phase, event, current_state, capabilities) -> (new_phase, effects)

Pure widget lifecycle reducer. Encodes the widget lifecycle as a deterministic
state machine with three phases, six event types, and five effect types.
No I/O, no side effects — the shell walks the returned effects.
"""
function reduce(
    phase::Phase,
    event::Any,
    current_state::Dict{String,Any},
    capabilities::TransportCapabilities,
)
    if event isa Open
        return _reduce_open(phase, current_state, capabilities)
    elseif event isa SendState
        return _reduce_send_state(phase, event, current_state, capabilities)
    elseif event isa SendCustom
        return _reduce_send_custom(phase, event, capabilities)
    elseif event isa Inbound
        return _reduce_inbound(phase, event, current_state, capabilities)
    elseif event isa Close
        return _reduce_close(phase)
    elseif event isa CommIdAssigned
        return OPEN, Any[]
    else
        return phase, Any[Error("unknown event type: $(typeof(event))")]
    end
end

function _reduce_open(
    phase::Phase,
    current_state::Dict{String,Any},
    capabilities::TransportCapabilities,
)
    if phase == UNOPENED || phase == CLOSED
        data, buffers, metadata = build_comm_open(
            merge(_immutable_fields(ANYWIDGET_MODULE_VERSION), current_state),
        )
        effects = Any[Send("comm_open", data; buffers=buffers, metadata=metadata)]
        if capabilities.supports_receive
            push!(effects, Listen())
        end
        return OPEN, effects
    end
    return OPEN, Any[]
end

function _reduce_send_state(
    phase::Phase,
    event::SendState,
    current_state::Dict{String,Any},
    capabilities::TransportCapabilities,
)
    if phase != OPEN
        return phase, Any[Error("send_state() requires an open comm; call open() first")]
    end
    if event.include === nothing
        state = merge(_immutable_fields(ANYWIDGET_MODULE_VERSION), current_state)
    else
        state = Dict{String,Any}(k => v for (k, v) in current_state if k in event.include)
    end
    data, buffers = build_update(state)
    return phase, Any[Send("comm_msg", data; buffers=buffers)]
end

function _reduce_send_custom(
    phase::Phase,
    event::SendCustom,
    capabilities::TransportCapabilities,
)
    if phase != OPEN
        return phase, Any[Error("send_custom() requires an open comm; call open() first")]
    end
    if !capabilities.supports_custom
        return phase, Any[Error("custom messages are not supported by this transport")]
    end
    if !capabilities.supports_buffers && !isempty(event.buffers)
        return phase, Any[Error("buffers are not supported by this transport")]
    end
    data = build_custom(event.content)
    return phase, Any[Send("comm_msg", data; buffers=event.buffers)]
end

function _reduce_inbound(
    phase::Phase,
    event::Inbound,
    current_state::Dict{String,Any},
    capabilities::TransportCapabilities,
)
    if phase != OPEN
        return phase, Any[]
    end
    message = parse_message(event.message)
    if message isa Update
        state = Dict{String,Any}(message.state)
        bufs = [Vector{UInt8}(b) for b in event.buffers]
        put_buffers!(state, message.buffer_paths, bufs)
        return phase, Any[ApplyState(state)]
    elseif message isa RequestState
        if !capabilities.supports_request_state
            return phase, Any[]
        end
        return _reduce_send_state(phase, SendState(), current_state, capabilities)
    elseif message isa Custom
        return phase, Any[InvokeCustom(message.content; buffers=Any[Vector{UInt8}(b) for b in event.buffers])]
    else
        return phase, Any[]
    end
end

function _reduce_close(phase::Phase)
    if phase == OPEN
        return CLOSED, Any[Send("comm_close", Dict{String,Any}())]
    end
    return phase, Any[]
end

# ---- imperative shell ----

"""
    WidgetShell(transport; get_state, set_state=nothing, model_id="", on_custom=nothing, capabilities=nothing)

Thin imperative shell that calls [`reduce`](@ref) and executes effects.
Replaces the old `Widget` mutable struct's lifecycle logic.
"""
mutable struct WidgetShell
    transport::Any
    get_state::Function
    set_state::Union{Function,Nothing}
    on_custom::Union{Function,Nothing}
    model_id::String
    phase::Phase
    capabilities::TransportCapabilities
    listening::Bool
end

function WidgetShell(
    transport;
    get_state::Function,
    set_state::Union{Function,Nothing}=nothing,
    model_id::AbstractString="",
    on_custom::Union{Function,Nothing}=nothing,
    capabilities::Union{TransportCapabilities,Nothing}=nothing,
)
    caps = if capabilities === nothing
        TransportCapabilities(
            supports_receive=supports_receive(transport),
            supports_request_state=supports_request_state(transport),
            supports_custom=supports_custom(transport),
            supports_buffers=supports_buffers(transport),
        )
    else
        capabilities
    end
    return WidgetShell(
        transport, get_state, set_state, on_custom,
        String(model_id), UNOPENED, caps, false,
    )
end

"Send the `comm_open` and start listening for inbound messages. Idempotent."
function open!(s::WidgetShell)
    s.phase == OPEN && return s
    _execute!(s, reduce(s.phase, Open(), s.get_state(), s.capabilities))
    return s
end

"Send an `update` with the full state, or only the keys in `include`."
function send_state!(s::WidgetShell; include=nothing)
    _execute!(s, reduce(s.phase, SendState(; include=include), s.get_state(), s.capabilities))
    return nothing
end

"Send a `custom` message to the frontend."
function send_custom!(s::WidgetShell, content; buffers=Any[])
    _execute!(s, reduce(s.phase, SendCustom(content; buffers=buffers), s.get_state(), s.capabilities))
    return nothing
end

"Close the comm channel. Idempotent."
function close!(s::WidgetShell)
    _execute!(s, reduce(s.phase, Close(), Dict{String,Any}(), s.capabilities))
    return nothing
end

"The widget-view mimebundle for display, referencing the shell's `model_id`."
mimebundle(s::WidgetShell, repr_text::AbstractString="") = mimebundle(s.model_id, repr_text)

# ---- internal: execute effects ----

function _execute!(s::WidgetShell, result::Tuple{Phase,Vector{Any}})
    new_phase, effects = result
    s.phase = new_phase
    for effect in effects
        _exec_one!(s, effect)
    end
    return nothing
end

function _exec_one!(s::WidgetShell, effect::Any)
    if effect isa Send
        transport_send(s.transport, effect.msg_type, effect.data;
                       buffers=effect.buffers, metadata=effect.metadata)
        if effect.msg_type == "comm_open"
            cid = comm_id(s.transport)
            if !isempty(cid)
                s.model_id = cid
                _execute!(s, reduce(s.phase, CommIdAssigned(cid), Dict{String,Any}(), s.capabilities))
            end
        end
    elseif effect isa Listen
        if !s.listening
            transport_on_message(s.transport, (d, b) -> _handle_inbound!(s, d, b))
            s.listening = true
        end
    elseif effect isa ApplyState
        if s.set_state !== nothing
            s.set_state(effect.state)
        end
    elseif effect isa InvokeCustom
        if s.on_custom !== nothing
            s.on_custom(effect.content, effect.buffers)
        end
    elseif effect isa Error
        error(effect.message)
    end
    return nothing
end

function _handle_inbound!(s::WidgetShell, data, buffers)
    message = parse_message(data)
    if message isa Update || message isa RequestState || message isa Custom
        _execute!(s, reduce(s.phase, Inbound(data; buffers=buffers), s.get_state(), s.capabilities))
    end
    return nothing
end

# ---- deprecated Widget wrapper (delegates to WidgetShell) ----

"Deprecated wrapper around WidgetShell. Kept for backward compatibility."
mutable struct Widget
    shell::WidgetShell
    model_id::String
    opened::Bool
end

function Widget(
    transport;
    get_state::Function,
    set_state::Union{Function,Nothing}=nothing,
    model_id::AbstractString="",
    on_custom::Union{Function,Nothing}=nothing,
)
    Base.depwarn("Widget is deprecated; use WidgetShell instead", :Widget)
    shell = WidgetShell(transport; get_state=get_state, set_state=set_state,
                         model_id=model_id, on_custom=on_custom)
    return Widget(shell, String(model_id), shell.phase == OPEN)
end

function open!(w::Widget)
    open!(w.shell)
    w.model_id = w.shell.model_id
    w.opened = true
    return w
end
function send_state!(w::Widget; include=nothing)
    send_state!(w.shell; include=include)
    w.model_id = w.shell.model_id
    return nothing
end
function send_custom!(w::Widget, content; buffers=Any[])
    send_custom!(w.shell, content; buffers=buffers)
    w.model_id = w.shell.model_id
    return nothing
end
function close!(w::Widget)
    close!(w.shell)
    w.model_id = w.shell.model_id
    w.opened = false
    return nothing
end
mimebundle(w::Widget, repr_text::AbstractString="") = mimebundle(w.shell, repr_text)

# ---- buffer split / merge (protocol v2 nested rules) ----

const _MAX_DEPTH = 500

function _separate(sub, path, buffer_paths, buffers, ancestors=Set{UInt64}(), depth=0)
    if !iscontainer(sub)
        return sub
    end
    if depth > _MAX_DEPTH
        error("state nesting exceeds $_MAX_DEPTH levels at path $path")
    end
    oid = objectid(sub)
    if oid in ancestors
        error("cyclic reference detected in state at path $path")
    end
    push!(ancestors, oid)
    try
        if sub isa AbstractDict
            out = Dict{String,Any}()
            for (k, v) in sub
                if isbinary(v)
                    push!(buffers, v)
                    push!(buffer_paths, Any[path..., k])
                elseif iscontainer(v)
                    out[k] = _separate(v, Any[path..., k], buffer_paths, buffers, ancestors, depth + 1)
                else
                    out[k] = v
                end
            end
            return out
        else  # AbstractVector
            out = Vector{Any}(undef, length(sub))
            for (i, v) in enumerate(sub)
                idx0 = i - 1  # wire protocol is 0-based
                if isbinary(v)
                    out[i] = nothing
                    push!(buffers, v)
                    push!(buffer_paths, Any[path..., idx0])
                elseif iscontainer(v)
                    out[i] = _separate(v, Any[path..., idx0], buffer_paths, buffers, ancestors, depth + 1)
                else
                    out[i] = v
                end
            end
            return out
        end
    finally
        delete!(ancestors, oid)
    end
end

"""
    remove_buffers(state) -> (state_without_buffers, buffer_paths, buffers)

Strip binary (`Vector{UInt8}`) values out of `state` into a parallel `buffers` list,
recording their locations in `buffer_paths` (dict keys as strings, array indices as
0-based integers).
"""
function remove_buffers(state)
    buffer_paths = Vector{Any}[]
    buffers = Any[]
    stripped = _separate(state, Any[], buffer_paths, buffers)
    return stripped, buffer_paths, buffers
end

"""
    put_buffers!(state, buffer_paths, buffers)

Inverse of [`remove_buffers`](@ref); mutates `state` in place. Integer path segments are
treated as 0-based (wire) indices and translated to Julia's 1-based indexing.
"""
function put_buffers!(state, buffer_paths, buffers)
    length(buffer_paths) == length(buffers) || error(
        "buffer_paths and buffers length mismatch: " *
        "$(length(buffer_paths)) != $(length(buffers))",
    )
    for (path, buf) in zip(buffer_paths, buffers)
        obj = state
        for key in path[1:(end - 1)]
            obj = key isa Integer ? obj[key + 1] : obj[key]
        end
        last = path[end]
        if last isa Integer
            obj[last + 1] = buf
        else
            obj[last] = buf
        end
    end
    return state
end

# ---- message builders ----
"""
    build_comm_open(state; anywidget_version=ANYWIDGET_MODULE_VERSION)
        -> (data, buffers, metadata)
"""
function build_comm_open(state; anywidget_version::AbstractString=ANYWIDGET_MODULE_VERSION)
    full = merge(_immutable_fields(anywidget_version), Dict{String,Any}(state))
    stripped, buffer_paths, buffers = remove_buffers(full)
    data = Dict{String,Any}("state" => stripped, "buffer_paths" => buffer_paths)
    metadata = Dict{String,Any}("version" => PROTOCOL_VERSION)
    return data, buffers, metadata
end

"""
    build_update(state) -> (data, buffers)
"""
function build_update(state)
    stripped, buffer_paths, buffers = remove_buffers(Dict{String,Any}(state))
    data = Dict{String,Any}(
        "method" => "update", "state" => stripped, "buffer_paths" => buffer_paths
    )
    return data, buffers
end

"Build a `custom` message payload."
build_custom(content) = Dict{String,Any}("method" => "custom", "content" => content)

# ---- serialization: widget-state JSON schema v2 (dump/load) ----

"""
    dump_model(entry; anywidget_version=ANYWIDGET_MODULE_VERSION) -> (model_id, record)

Serialize one `(model_id, state)` entry to a schema-v2 record. The anywidget identity
(`model_name`/`model_module`/`model_module_version`) is read from `state` if the host set
the `_model_*` fields, else defaulted to the `AnyModel`/`anywidget` frontend. Binary
(`Vector{UInt8}`) values move to a base64 `buffers` array; the rest of `state` is
preserved verbatim so [`load_model`](@ref) is the exact inverse.
"""
function dump_model(entry; anywidget_version::AbstractString=ANYWIDGET_MODULE_VERSION)
    model_id, state = entry
    stripped, buffer_paths, buffers = remove_buffers(state)
    record = Dict{String,Any}(
        "model_name" => get(state, "_model_name", "AnyModel"),
        "model_module" => get(state, "_model_module", "anywidget"),
        "model_module_version" => get(state, "_model_module_version", anywidget_version),
        "state" => stripped,
    )
    if !isempty(buffers)
        record["buffers"] = [
            Dict{String,Any}(
                "path" => path, "encoding" => "base64", "data" => base64encode(buf)
            ) for (path, buf) in zip(buffer_paths, buffers)
        ]
    end
    return model_id, record
end

"""
    load_model((model_id, record)) -> (model_id, state)

Inverse of [`dump_model`](@ref): rebuild `(model_id, state)` from a record. Base64 buffers
are decoded to `Vector{UInt8}` and merged into a *copy* of `record["state"]`, so the input
record (and any document holding it) is not mutated — load is pure (cositos-t3c).
"""
function load_model(item)
    model_id, record = item
    state = deepcopy(record["state"])
    entries = get(record, "buffers", [])
    buffer_paths = [e["path"] for e in entries]
    buffers = [_decode_buffer(e) for e in entries]
    put_buffers!(state, buffer_paths, buffers)
    return model_id, state
end

function _decode_buffer(entry)
    encoding = get(entry, "encoding", nothing)
    encoding == "base64" ||
        error("Unsupported buffer encoding: $(repr(encoding)) (expected 'base64')")
    return base64decode(entry["data"])
end

"""
    dump_document(entries; anywidget_version=ANYWIDGET_MODULE_VERSION) -> Document

Serialize many `(model_id, state)` entries into a v2 Widget-State envelope
`{version_major, version_minor, state}`, where `state` maps each `model_id` to its record.
Model ids must be non-empty and unique (they are the document keys). Composed UIs need
nothing special: children stored as `"IPY_MODEL_<id>"` strings round-trip verbatim.
"""
function dump_document(entries; anywidget_version::AbstractString=ANYWIDGET_MODULE_VERSION)
    state = Dict{String,Any}()
    for entry in entries
        model_id, record = dump_model(entry; anywidget_version=anywidget_version)
        isempty(model_id) &&
            error("model_id must be a non-empty string (it is the document key)")
        haskey(state, model_id) &&
            error("duplicate model_id $(repr(model_id)): document keys must be unique")
        state[model_id] = record
    end
    return Dict{String,Any}(
        "version_major" => STATE_VERSION_MAJOR,
        "version_minor" => STATE_VERSION_MINOR,
        "state" => state,
    )
end

"""
    load_document(doc) -> Vector{Tuple{String,Any}}

Inverse of [`dump_document`](@ref): rebuild the list of `(model_id, state)`. References
between models are plain `"IPY_MODEL_<id>"` strings, so loading is a flat id-keyed pass
(reference cycles are safe — no recursive inlining).
"""
load_document(doc) = [load_model(item) for item in doc["state"]]

"""
    with_view_identity(document) -> Document

Return a copy of `document` with anywidget *view* identity merged into each model's
`state` — the form the CDN html-manager needs to render.

Parity with Python's `cositos.embed.with_view_identity`. [`dump_document`](@ref) stays a
lossless codec that certifies byte-for-byte against the shared golden fixture; view
identity is a static-*rendering* concern, so it is injected here (the analog of the live
`build_comm_open` path) rather than in the serialized document. Host-set state wins over
the injected defaults. Julia has no static-export/embed host yet; this provides the
enrichment a future one would apply before handing state to the html-manager.
"""
function with_view_identity(document)
    records = get(document, "state", Dict{String,Any}())
    enriched = Dict{String,Any}()
    for (model_id, record) in records
        version = get(record, "model_module_version", ANYWIDGET_MODULE_VERSION)
        state = merge(view_identity(version), get(record, "state", Dict{String,Any}()))
        enriched[model_id] = merge(record, Dict{String,Any}("state" => state))
    end
    return merge(document, Dict{String,Any}("state" => enriched))
end

"Build the widget-view mimebundle used for display."
function mimebundle(model_id::AbstractString, repr_text::AbstractString="")
    bundle = Dict{String,Any}(
        WIDGET_VIEW_MIMETYPE => Dict{String,Any}(
            "version_major" => PROTOCOL_VERSION_MAJOR,
            "version_minor" => PROTOCOL_VERSION_MINOR,
            "model_id" => model_id,
        ),
    )
    isempty(repr_text) || (bundle["text/plain"] = repr_text)
    return bundle
end

# ---- inbound parsing ----

struct Update
    state::Any
    buffer_paths::Any
end
struct RequestState end
struct Custom
    content::Any
end
struct Ignored
    method::Any
end

Base.:(==)(a::Update, b::Update) = a.state == b.state && a.buffer_paths == b.buffer_paths
Base.:(==)(a::Custom, b::Custom) = a.content == b.content
Base.:(==)(a::Ignored, b::Ignored) = a.method == b.method

"""
    parse_message(data) -> Union{Update,RequestState,Custom,Ignored}

Parse an inbound `comm_msg` `data` dict into a typed event. An unknown or missing `method`
yields `Ignored` (never throws), matching ipywidgets' forward-compatible dispatch
(cositos-05i/dow).
"""
function parse_message(data)
    method = get(data, "method", nothing)
    method == "update" &&
        return Update(get(data, "state", Dict{String,Any}()), get(data, "buffer_paths", []))
    method == "request_state" && return RequestState()
    method == "custom" && return Custom(get(data, "content", nothing))
    return Ignored(method)
end

# ---- Widget façade + Transport contract (kernel-agnostic) ----

"""Whether the transport can receive frontend→kernel messages (one-way otherwise)."""
supports_receive(::Any) = false

"Whether the transport supports request_state responses."
supports_request_state(::Any) = true
supports_request_state(::Nothing) = false

"Whether the transport supports custom messages."
supports_custom(::Any) = true
supports_custom(::Nothing) = false

"Whether the transport supports binary buffers."
supports_buffers(::Any) = true
supports_buffers(::Nothing) = false

"""The transport's comm id (widget `model_id`); empty until opened."""
comm_id(::Any) = ""

"""
    transport_send(transport, msg_type, content; buffers=Any[], metadata=nothing)

Send a Jupyter comm message (`comm_open` / `comm_msg` / `comm_close`) to the frontend.
"""
function transport_send end

"""
    transport_on_message(transport, callback)

Register `callback(data, buffers)`, invoked for each inbound `comm_msg`.
"""
function transport_on_message end

"""
    ijulia_transport() -> transport

Construct an IJulia comm transport for driving a [`Widget`](@ref) inside a live IJulia
(Julia Jupyter) kernel. The implementation lives in the `CositosIJuliaExt` package
extension and is available only once `IJulia` is loaded (`using IJulia`); calling this
without IJulia raises a hint.
"""
function ijulia_transport(args...; kwargs...)
    return error(
        "ijulia_transport() requires IJulia to be loaded; run `using IJulia` first " *
        "(the CositosIJuliaExt package extension provides the implementation).",
    )
end

# ---- Real @jupyter-widgets/controls catalog (see ext/CositosControlsExt.jl) ----

function int_slider(args...; kwargs...)
    return error(
        "int_slider() requires JSON to be loaded; run `using JSON` first " *
        "(the CositosControlsExt package extension provides the implementation).",
    )
end

function dropdown(args...; kwargs...)
    return error(
        "dropdown() requires JSON to be loaded; run `using JSON` first " *
        "(the CositosControlsExt package extension provides the implementation).",
    )
end

function vbox(args...; kwargs...)
    return error(
        "vbox() requires JSON to be loaded; run `using JSON` first " *
        "(the CositosControlsExt package extension provides the implementation).",
    )
end

function hbox(args...; kwargs...)
    return error(
        "hbox() requires JSON to be loaded; run `using JSON` first " *
        "(the CositosControlsExt package extension provides the implementation).",
    )
end

"""
    local_front_runtime_url() -> String

A `data:` URI embedding a self-contained bundle of `@cositos/front` (`front/src/*.js`)
with no relative imports. Requires `JSON` and `AbstractPlutoDingetjes`.
"""
function local_front_runtime_url(args...; kwargs...)
    return error(
        "local_front_runtime_url() requires JSON and AbstractPlutoDingetjes to be " *
        "loaded; run `using JSON, AbstractPlutoDingetjes` first (the CositosPlutoExt " *
        "package extension provides the implementation).",
    )
end

const DEFAULT_RUNTIME_URL = "https://cdn.jsdelivr.net/npm/@cositos/front/src/index.js"

struct PlutoWidget
    esm::String
    state::Dict{String,Any}
    css::String
    runtime_url::String
end

function PlutoWidget(;
    esm::AbstractString,
    state=Dict{String,Any}(),
    css::AbstractString="",
    runtime_url::AbstractString=DEFAULT_RUNTIME_URL,
)
    return PlutoWidget(String(esm), Dict{String,Any}(state), String(css), String(runtime_url))
end

module Pluto

const _ERROR_SUFFIX = " requires JSON and AbstractPlutoDingetjes to be loaded; run " *
    "`using JSON, AbstractPlutoDingetjes` first (the CositosPlutoExt package " *
    "extension provides the implementation)."

function int_slider(args...; kwargs...)
    return error("Cositos.Pluto.int_slider()" * _ERROR_SUFFIX)
end
function checkbox(args...; kwargs...)
    return error("Cositos.Pluto.checkbox()" * _ERROR_SUFFIX)
end
function text(args...; kwargs...)
    return error("Cositos.Pluto.text()" * _ERROR_SUFFIX)
end
function button(args...; kwargs...)
    return error("Cositos.Pluto.button()" * _ERROR_SUFFIX)
end
function dropdown(args...; kwargs...)
    return error("Cositos.Pluto.dropdown()" * _ERROR_SUFFIX)
end
function html(args...; kwargs...)
    return error("Cositos.Pluto.html()" * _ERROR_SUFFIX)
end

end # module Pluto

end # module