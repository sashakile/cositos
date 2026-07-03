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

export PROTOCOL_VERSION, ANYWIDGET_MODULE_VERSION,
    build_comm_open, build_update, build_custom, mimebundle,
    parse_message, Update, RequestState, Custom,
    remove_buffers, put_buffers!

const PROTOCOL_VERSION_MAJOR = 2
const PROTOCOL_VERSION_MINOR = 1
const PROTOCOL_VERSION = "$(PROTOCOL_VERSION_MAJOR).$(PROTOCOL_VERSION_MINOR).0"

const TARGET_NAME = "jupyter.widget"
const WIDGET_VIEW_MIMETYPE = "application/vnd.jupyter.widget-view+json"

"Default anywidget frontend semver range this backend targets."
const ANYWIDGET_MODULE_VERSION = "~0.11.*"

isbinary(x) = x isa Vector{UInt8}
iscontainer(x) = (x isa AbstractDict || x isa AbstractVector) && !isbinary(x)

function _immutable_fields(version::AbstractString)
    return Dict{String,Any}(
        "_model_module" => "anywidget",
        "_model_name" => "AnyModel",
        "_model_module_version" => version,
        "_view_module" => "anywidget",
        "_view_name" => "AnyView",
        "_view_module_version" => version,
        "_view_count" => nothing,
    )
end

# ---- buffer split / merge (protocol v2 nested rules) ----

function _separate(sub, path, buffer_paths, buffers)
    if sub isa AbstractDict
        out = Dict{String,Any}()
        for (k, v) in sub
            if isbinary(v)
                push!(buffers, v)
                push!(buffer_paths, Any[path..., k])
            elseif iscontainer(v)
                out[k] = _separate(v, Any[path..., k], buffer_paths, buffers)
            else
                out[k] = v
            end
        end
        return out
    elseif sub isa AbstractVector
        out = Vector{Any}(undef, length(sub))
        for (i, v) in enumerate(sub)
            idx0 = i - 1  # wire protocol is 0-based
            if isbinary(v)
                out[i] = nothing
                push!(buffers, v)
                push!(buffer_paths, Any[path..., idx0])
            elseif iscontainer(v)
                out[i] = _separate(v, Any[path..., idx0], buffer_paths, buffers)
            else
                out[i] = v
            end
        end
        return out
    else
        return sub
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

Base.:(==)(a::Update, b::Update) = a.state == b.state && a.buffer_paths == b.buffer_paths
Base.:(==)(a::Custom, b::Custom) = a.content == b.content

"""
    parse_message(data) -> Union{Update,RequestState,Custom}

Parse an inbound `comm_msg` `data` dict into a typed event. Throws on an unknown method.
"""
function parse_message(data)
    method = get(data, "method", nothing)
    method == "update" &&
        return Update(get(data, "state", Dict{String,Any}()), get(data, "buffer_paths", []))
    method == "request_state" && return RequestState()
    method == "custom" && return Custom(get(data, "content", nothing))
    error("Unrecognized comm message method: $(repr(method))")
end

end # module
