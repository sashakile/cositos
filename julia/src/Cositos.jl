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
    parse_message, Update, RequestState, Custom,
    remove_buffers, put_buffers!,
    dump_model, load_model, dump_document, load_document,
    view_identity, with_view_identity,
    PlutoWidget

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
are decoded to `Vector{UInt8}` and merged back into `state` in place.
"""
function load_model(item)
    model_id, record = item
    state = record["state"]
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

# ---- Pluto.jl host (see ext/CositosPlutoExt.jl for the render + Bonds glue) ----

"""Default ESM URL for `@cositos/front` used by [`PlutoWidget`](@ref) rendering."""
const DEFAULT_RUNTIME_URL = "https://cdn.jsdelivr.net/npm/@cositos/front/src/index.js"

"""
    PlutoWidget(; esm, state=Dict(), css="", runtime_url=DEFAULT_RUNTIME_URL)

A Pluto.jl-displayable anywidget: renders `esm` via `@cositos/front` and acts as an
`@bind` target. `Base.show(::MIME"text/html")` and the `AbstractPlutoDingetjes.Bonds`
methods live in the package extension `CositosPlutoExt`, which loads automatically when
`AbstractPlutoDingetjes` and `JSON` are available.

```julia
using Cositos, AbstractPlutoDingetjes   # extension activates
@bind s PlutoWidget(esm=SLIDER_ESM, state=Dict("value" => 0, "min" => 0, "max" => 100))
# `s` becomes the widget's full state Dict, updated reactively on interaction.
```
"""
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

end # module
