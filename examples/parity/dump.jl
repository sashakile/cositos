# Emit the same widget-state Document as the Python reference, from the Julia port.
# Run:  julia --project=examples/parity examples/parity/dump.jl
# Prints the serialized Document as canonical JSON (indent=2) to stdout, so a parity
# check (or a Quarto tab) can compare it against Python's dump_document output.
using Cositos, JSON

const ESM = "export default { render({ model, el }) { el.textContent = model.get(\"value\"); } }"

doc = dump_document([("counter", Dict{String,Any}("_esm" => ESM, "value" => 42))])
println(JSON.json(doc, 2))
