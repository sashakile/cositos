"""
CositosControlsExt — real `@jupyter-widgets/controls`/`base` catalog for cositos (Julia
port of Python's `cositos.contrib.controls`, cositos-70b.7).

Loads automatically when `JSON` is available. Provides [`Cositos.int_slider`](@ref),
[`Cositos.dropdown`](@ref), [`Cositos.vbox`](@ref), [`Cositos.hbox`](@ref) \u2014 thin builders
that reuse the real ipywidgets frontend zoo's own identity verbatim (pinned at module
version `2.0.0`, the design note's choice) by reading the SAME shared catalog JSON the
Python builder reads (`../../fixtures/controls-catalog.json`), not a re-derived copy.
cositos' anti-goal is *reimplementing* the ipywidgets widget zoo (`docs/widgets.md`);
this module does not.

Scope is intentionally trimmed (YAGNI, matches the Python builder) to exactly
`IntSlider`, `Dropdown`, `VBox`, `HBox` and their required companion models \u2014 see
`.wai/projects/cositos-core/designs/2026-07-09-design-controls-catalog-schema-and-scope.md`.

**Id-uniqueness rule**: every call mints a fresh `model_id` (via `UUIDs.uuid4()`) for the
widget itself and each companion \u2014 the catalog's own placeholder strings
(`IPY_MODEL_<slider_style_id>` etc.) are schema documentation, never reused as real ids
(`dump_document` rejects duplicate `model_id`s).

**Dropdown wire-field correction (parity with the Python builder, found by that ticket's
real-browser check, not visible from trait names alone)**: `Dropdown`'s `options`/`value`
traits carry no `sync=True` tag in ipywidgets \u2014 only `_options_labels` (label strings)
and a 0-based `index` are ever on the wire; [`Cositos.dropdown`](@ref) translates its
ergonomic `options`/`value` parameters accordingly.
"""
module CositosControlsExt

using Cositos: Cositos
import JSON
using UUIDs: uuid4

const _CATALOG_PATH = joinpath(@__DIR__, "..", "..", "fixtures", "controls-catalog.json")
const _CATALOG = JSON.parsefile(_CATALOG_PATH)

_mint_id(root_id::AbstractString, role::AbstractString) = "$(root_id)-$(role)"

function _identity(spec)
    return Dict{String,Any}(
        "_model_name" => spec["model_name"],
        "_model_module" => spec["model_module"],
        "_model_module_version" => spec["model_module_version"],
        "_view_name" => spec["view_name"],
        "_view_module" => spec["view_module"],
        "_view_module_version" => spec["view_module_version"],
    )
end

"""
    _build(catalog_key, overrides; model_id=nothing) -> Vector{Tuple{String,Dict{String,Any}}}

Build one catalog entry's widget + its freshly id'd companion models. The widget's own
entry is always first in the returned list, followed by one entry per companion (order
matches the catalog's `companions` list). Mirrors Python's `controls._build`.
"""
function _build(
    catalog_key::AbstractString,
    overrides::AbstractDict;
    model_id::Union{Nothing,AbstractString}=nothing,
)
    spec = _CATALOG[catalog_key]
    root_id = model_id === nothing ? replace(string(uuid4()), "-" => "") : String(model_id)

    state = Dict{String,Any}(spec["default_state"])
    companion_entries = Tuple{String,Dict{String,Any}}[]
    for companion in spec["companions"]
        key = companion["key_in_default_state"]
        companion_id = _mint_id(root_id, key)
        state[key] = "IPY_MODEL_$(companion_id)"
        companion_state = Dict{String,Any}(
            "_model_name" => companion["model_name"],
            "_model_module" => companion["model_module"],
            "_model_module_version" => companion["model_module_version"],
            "_view_name" => companion["view_name"],
            "_view_module" => companion["view_module"],
            "_view_module_version" => companion["view_module_version"],
        )
        push!(companion_entries, (companion_id, companion_state))
    end

    for (k, v) in overrides
        state[k] = v
    end
    widget_state = merge(_identity(spec), state)
    return vcat([(root_id, widget_state)], companion_entries)
end

_str_dict(kwargs) = Dict{String,Any}(String(k) => v for (k, v) in kwargs)

"""
    Cositos.int_slider(; value=0, min=0, max=100, kwargs...)

A real `@jupyter-widgets/controls` `IntSliderModel` + its style/layout companions.
"""
function Cositos.int_slider(; value::Integer=0, min::Integer=0, max::Integer=100, kwargs...)
    overrides = _str_dict(kwargs)
    overrides["value"] = value
    overrides["min"] = min
    overrides["max"] = max
    return _build("int_slider", overrides)
end

"""
    Cositos.dropdown(options; value=nothing, kwargs...)

A real `@jupyter-widgets/controls` `DropdownModel` + its style/layout companions. See the
module docstring for the `_options_labels`/`index` wire-field correction. Pass `index=`
directly in `kwargs` to bypass the `value`-to-`index` lookup.
"""
function Cositos.dropdown(options; value=nothing, kwargs...)
    labels = [string(option) for option in options]
    overrides = _str_dict(kwargs)
    index = pop!(overrides, "index", nothing)
    if index === nothing && value !== nothing
        str_value = string(value)
        found = findfirst(==(str_value), labels)
        index = found === nothing ? nothing : found - 1  # 0-based wire index
    end
    overrides["_options_labels"] = labels
    overrides["index"] = index
    return _build("dropdown", overrides)
end

function _box(catalog_key::AbstractString, children; kwargs...)
    child_refs = ["IPY_MODEL_$(child[1][1])" for child in children]
    overrides = _str_dict(kwargs)
    overrides["children"] = child_refs
    own = _build(catalog_key, overrides)
    descendants = isempty(children) ? Tuple{String,Dict{String,Any}}[] : vcat(children...)
    return vcat(own, descendants)
end

"""
    Cositos.vbox(children; kwargs...)

A real `@jupyter-widgets/controls` `VBoxModel` laying out `children` (a list of
previously built entries-lists) vertically \u2014 this widget's `children` trait references
each child's root id, and the returned entries list flattens in every descendant so the
whole tree serializes as one document.
"""
Cositos.vbox(children; kwargs...) = _box("vbox", children; kwargs...)

"""
    Cositos.hbox(children; kwargs...)

See [`Cositos.vbox`](@ref) for the `children` composition contract (identical, horizontal
layout only).
"""
Cositos.hbox(children; kwargs...) = _box("hbox", children; kwargs...)

end # module
