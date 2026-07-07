using Test
using Base64
using JSON
using AbstractPlutoDingetjes
using Cositos

const FIXTURES = joinpath(@__DIR__, "..", "..", "fixtures")

"Recursive JSON-structural equality, tolerant of concrete container/number types."
function jsonequal(a, b)
    if a isa AbstractDict && b isa AbstractDict
        keys(a) == keys(b) || return false
        return all(jsonequal(a[k], b[k]) for k in keys(a))
    elseif a isa AbstractVector && b isa AbstractVector
        length(a) == length(b) || return false
        return all(jsonequal(x, y) for (x, y) in zip(a, b))
    elseif a isa Number && b isa Number
        return a == b
    else
        return a == b
    end
end

b64(buffers) = [base64encode(b) for b in buffers]

@testset "Cositos" begin
    @testset "buffers: flat dict extracts binary by key" begin
        state = Dict{String,Any}("n" => 1, "blob" => UInt8[1, 2])
        stripped, paths, buffers = remove_buffers(state)
        @test stripped == Dict{String,Any}("n" => 1)
        @test paths == [["blob"]]
        @test buffers == [UInt8[1, 2]]
    end

    @testset "buffers: list slots become nothing with 0-based paths" begin
        b = UInt8[9]
        stripped, paths, buffers = remove_buffers(Dict{String,Any}("xs" => Any[b, 2, b]))
        @test stripped == Dict{String,Any}("xs" => Any[nothing, 2, nothing])
        @test paths == [["xs", 0], ["xs", 2]]   # 0-based wire indices
        @test length(buffers) == 2
    end

    @testset "buffers: nested round-trip is lossless" begin
        original = Dict{String,Any}(
            "x" => Dict{String,Any}("ar" => UInt8[1]),
            "y" => Any[UInt8[2], 3, Dict{String,Any}("z" => UInt8[4])],
        )
        stripped, paths, buffers = remove_buffers(original)
        put_buffers!(stripped, paths, buffers)
        @test stripped == original
    end

    @testset "parse_message" begin
        @test parse_message(Dict("method" => "update", "state" => Dict("a" => 1),
            "buffer_paths" => [])) == Update(Dict("a" => 1), [])
        @test parse_message(Dict("method" => "request_state")) == RequestState()
        @test parse_message(Dict("method" => "custom", "content" => 42)) == Custom(42)
        @test_throws ErrorException parse_message(Dict("method" => "bogus"))
    end

    @testset "mimebundle" begin
        view = mimebundle("abc")[Cositos.WIDGET_VIEW_MIMETYPE]
        @test view == Dict{String,Any}(
            "version_major" => 2, "version_minor" => 1, "model_id" => "abc"
        )
    end

    # ---- conformance against the shared golden fixtures ----
    @testset "conformance: comm_open" begin
        fx = JSON.parsefile(joinpath(FIXTURES, "comm_open.json"))
        data, buffers, metadata = build_comm_open(
            Dict{String,Any}("_esm" => "export default { render() {} }", "value" => 0)
        )
        @test jsonequal(data, fx["data"])
        @test b64(buffers) == fx["buffers_b64"]
        @test jsonequal(metadata, fx["metadata"])
    end

    @testset "conformance: update" begin
        fx = JSON.parsefile(joinpath(FIXTURES, "update.json"))
        data, buffers = build_update(Dict{String,Any}("value" => 42))
        @test jsonequal(data, fx["data"])
        @test b64(buffers) == fx["buffers_b64"]
    end

    @testset "conformance: update with nested buffer" begin
        fx = JSON.parsefile(joinpath(FIXTURES, "update_nested_buffer.json"))
        data, buffers = build_update(Dict{String,Any}(
            "img" => Dict{String,Any}("bytes" => Vector{UInt8}("PNGDATA")),
            "shape" => Any[1, 1],
        ))
        @test jsonequal(data, fx["data"])
        @test b64(buffers) == fx["buffers_b64"]
    end

    @testset "conformance: custom" begin
        fx = JSON.parsefile(joinpath(FIXTURES, "custom.json"))
        @test jsonequal(build_custom(Dict{String,Any}("event" => "click", "n" => 3)), fx["data"])
    end

    # ---- serialization: dump/load_document, certified vs widget-state.json ----
    plot_bytes() = collect(reinterpret(UInt8, Float32[1.5, 2.5, -3.0]))

    function widget_state_entries()
        return [
            ("box", Dict{String,Any}(
                "_esm" => "export default { render({model, el}) { /* VBox */ } }",
                "children" => Any["IPY_MODEL_plot"],
            )),
            ("plot", Dict{String,Any}(
                "_esm" => "export default { render({model, el}) { /* float32 plot */ } }",
                "shape" => Any[3],
                "dtype" => "float32",
                "data" => plot_bytes(),
            )),
        ]
    end

    @testset "serialize: dump_document reproduces the golden fixture" begin
        fx = JSON.parsefile(joinpath(FIXTURES, "widget-state.json"))
        @test jsonequal(dump_document(widget_state_entries()), fx)
    end

    @testset "serialize: base64 buffer codec matches the fixture string" begin
        _, record = dump_model(("plot", Dict{String,Any}(
            "_esm" => "e", "shape" => Any[3], "dtype" => "float32", "data" => plot_bytes(),
        )))
        @test record["buffers"][1]["path"] == ["data"]
        @test record["buffers"][1]["encoding"] == "base64"
        @test record["buffers"][1]["data"] == "AADAPwAAIEAAAEDA"
    end

    @testset "serialize: load_document reconstructs entries (composition + raw bytes)" begin
        fx = JSON.parsefile(joinpath(FIXTURES, "widget-state.json"))
        loaded = load_document(fx)
        by_id = Dict(loaded)
        @test Set(mid for (mid, _) in loaded) == Set(["box", "plot"])
        @test by_id["box"]["children"] == ["IPY_MODEL_plot"]      # ref survives
        @test by_id["plot"]["data"] == plot_bytes()               # float32 buffer, raw bytes
    end

    @testset "serialize: buffer-free document round-trips both ways" begin
        entries = [
            ("box", Dict{String,Any}("children" => Any["IPY_MODEL_child"])),
            ("child", Dict{String,Any}("value" => 42)),
        ]
        by_id = Dict(load_document(dump_document(entries)))
        @test by_id["box"]["children"] == ["IPY_MODEL_child"]
        @test by_id["child"]["value"] == 42
        doc = dump_document(entries)
        @test jsonequal(dump_document(load_document(doc)), doc)
    end

    @testset "embed: with_view_identity injects anywidget view identity (cositos-e4j)" begin
        # Parity with Python's cositos.embed.with_view_identity: static rendering (the CDN
        # html-manager) needs each model's state to carry the anywidget view identity, or
        # it cannot pick a view class. dump_document stays a pure lossless codec (certified
        # vs the golden fixture above); the view identity is injected at this embed layer.
        entries = [("counter", Dict{String,Any}("_esm" => "e", "n" => 3))]
        doc = dump_document(entries)
        # dump stays pure: no view identity leaked into the serialized document.
        @test !haskey(doc["state"]["counter"]["state"], "_view_name")
        enriched = with_view_identity(doc)
        st = enriched["state"]["counter"]["state"]
        @test st["_view_name"] == "AnyView"
        @test st["_view_module"] == "anywidget"
        @test haskey(st, "_view_module_version")
        @test haskey(st, "_view_count")
        @test st["n"] == 3               # user state preserved
        # Host-set view identity wins over the injected defaults.
        entries2 = [("vbox", Dict{String,Any}("_view_name" => "VBoxView"))]
        st2 = with_view_identity(dump_document(entries2))["state"]["vbox"]["state"]
        @test st2["_view_name"] == "VBoxView"
    end

    @testset "serialize: dump_document validates model ids" begin
        @test_throws ErrorException dump_document([("", Dict{String,Any}("value" => 1))])
        @test_throws ErrorException dump_document([
            ("dup", Dict{String,Any}("value" => 1)),
            ("dup", Dict{String,Any}("value" => 2)),
        ])
    end

    @testset "serialize: load_model rejects a non-base64 buffer encoding" begin
        record = Dict{String,Any}(
            "state" => Dict{String,Any}("data" => nothing),
            "buffers" => [Dict{String,Any}("path" => ["data"], "encoding" => "hex", "data" => "00")],
        )
        @test_throws ErrorException load_model(("m", record))
    end

    @testset "put_buffers! rejects a buffer_paths/buffers length mismatch (cositos-y07)" begin
        # A mismatch must error, not silently leave a placeholder or drop a buffer.
        @test_throws ErrorException put_buffers!(
            Dict{String,Any}("a" => nothing, "b" => nothing), Any[["a"], ["b"]], Any[UInt8[1]]
        )
        @test_throws ErrorException put_buffers!(
            Dict{String,Any}("a" => nothing), Any[["a"]], Any[UInt8[1], UInt8[2]]
        )
    end

    @testset "Pluto extension: Bonds + HTML render contract" begin
        esm = "export default { render({model, el}) {} }"
        w = PlutoWidget(; esm=esm, state=Dict{String,Any}("value" => 0, "min" => 0, "max" => 100))

        # Bonds: the bound variable is the full state Dict; JS values pass through.
        @test AbstractPlutoDingetjes.Bonds.initial_value(w) == w.state
        @test AbstractPlutoDingetjes.Bonds.transform_value(w, Dict("value" => 55)) ==
            Dict("value" => 55)

        # HTML render upholds the @bind contract: imports the runtime, embeds ESM +
        # state, wires a PlutoChannel to the container element.
        html = sprint(show, MIME("text/html"), w)
        @test occursin("document.currentScript.parentElement", html)
        @test occursin("PlutoChannel", html)
        @test occursin("loadWidget", html)
        @test occursin(w.runtime_url, html)
        @test occursin("\"value\":0", replace(html, " " => ""))  # state embedded
        @test occursin("render({model, el})", html)                # esm embedded
    end
end
