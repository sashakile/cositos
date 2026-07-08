#!/usr/bin/env julia
# Julia implementation of the cross-language e2e contract (cositos-1wi.3).
#
# See examples/e2e/README.md for the full contract. This program:
#
#   1. builds the FIXED input (an anywidget counter, {_esm, value: 42}) into a
#      widget-state Document via Cositos.dump_document;
#   2. asserts the round-trip law load(dump(x)) == x via Cositos.load_document;
#   3. diffs the produced document against the pinned expected.json shared by every
#      language example (../expected.json, one level up from this directory);
#   4. prints "OK julia" and exits 0 on success, or a readable diff and a non-zero exit
#      on any divergence.
#
# Run it with `mise run e2e-julia` (or `julia --project=examples/e2e/julia
# examples/e2e/julia/dump.jl` from the repo root).
#
# NOTE (cositos-1wi.3): this is a *separate* program from examples/parity/dump.jl, which
# only prints dump_document's JSON and still drives the docs/tutorials/polyglot-parity.qmd
# render at build time. Reusing it here would couple this self-checking e2e contract to
# that docs page; keeping them independent means neither can break the other.

using Cositos, JSON

const HERE = @__DIR__
const ESM = "export default { render({ model, el }) { el.textContent = model.get(\"value\"); } }"
const MODEL_ID = "counter"

# The FIXED input state the whole contract is pinned to (see README "The fixed input").
const INPUT_STATE = Dict{String,Any}("_esm" => ESM, "value" => 42)

"""Serialize the fixed counter into a widget-state Document."""
build_document() = dump_document([(MODEL_ID, deepcopy(INPUT_STATE))])

"""The pinned golden document this port certifies against."""
load_expected() = JSON.parsefile(joinpath(HERE, "..", "expected.json"))

"""Check load(dump(x)) == x; return failure messages (empty means it holds)."""
function round_trip_failures()
    loaded = load_document(build_document())
    expected_entries = [(MODEL_ID, INPUT_STATE)]
    loaded == expected_entries && return String[]
    return ["round-trip law violated: load(dump(x)) = $(repr(loaded)), expected $(repr(expected_entries))"]
end

"""Human-readable line diff between expected and actual pretty-printed JSON."""
function json_diff(expected, actual)
    expected == actual && return String[]
    exp_lines = split(JSON.json(expected, 2), '\n')
    act_lines = split(JSON.json(actual, 2), '\n')
    out = ["produced document diverges from expected.json:"]
    n = max(length(exp_lines), length(act_lines))
    for i in 1:n
        e = i <= length(exp_lines) ? exp_lines[i] : nothing
        a = i <= length(act_lines) ? act_lines[i] : nothing
        if e != a
            e !== nothing && push!(out, "- $e")
            a !== nothing && push!(out, "+ $a")
        end
    end
    return out
end

"""Run the full contract; return a list of failure messages (empty means pass)."""
verify(expected) = vcat(round_trip_failures(), json_diff(expected, build_document()))

function main()
    failures = verify(load_expected())
    if !isempty(failures)
        for line in failures
            println(stderr, line)
        end
        exit(1)
    end
    println("OK julia")
    exit(0)
end

main()
