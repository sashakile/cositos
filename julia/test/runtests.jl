using Test
using Base64
using JSON
using AbstractPlutoDingetjes
using Cositos
using Cositos.Pluto
using Cositos.Pluto: int_slider as _pluto_int_slider_selective  # proves the selective-using call style

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

    @testset "buffers: cycle detection raises clear error" begin
        state = Dict{String,Any}("a" => 1)
        state["self"] = state
        @test_throws ErrorException remove_buffers(state)
    end

    @testset "buffers: depth capping raises clear error" begin
        state = Dict{String,Any}()
        node = state
        for _ in 1:2000
            child = Dict{String,Any}()
            node["n"] = child
            node = child
        end
        @test_throws ErrorException remove_buffers(state)
    end

    @testset "buffers: shared acyclic subtrees (DAG) are fine" begin
        shared = Dict{String,Any}("v" => 1)
        state = Dict{String,Any}("a" => shared, "b" => shared)
        stripped, paths, buffers = remove_buffers(state)
        @test stripped == Dict{String,Any}("a" => Dict{String,Any}("v" => 1), "b" => Dict{String,Any}("v" => 1))
        @test paths == []
        @test buffers == []
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
        # Unknown/missing method is ignored, not thrown (forward-compat, cositos-dow).
        @test parse_message(Dict("method" => "bogus")) == Ignored("bogus")
        @test parse_message(Dict("method" => "echo_update")) == Ignored("echo_update")
        @test parse_message(Dict{String,Any}()) == Ignored(nothing)
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

    @testset "load_document does not mutate the input document (cositos-t3c)" begin
        # load must be pure: mutating record["state"] in place would merge raw bytes back
        # into the input document, breaking a later re-dump/embed.
        entries = [("plot", Dict{String,Any}(
            "_esm" => "e", "shape" => Any[3], "dtype" => "float32", "data" => plot_bytes(),
        ))]
        doc = dump_document(entries)
        doc_before = deepcopy(doc)
        loaded = load_document(doc)
        @test doc == doc_before                              # input unchanged
        @test Dict(loaded)["plot"]["data"] == plot_bytes()   # load still reconstructs bytes
    end

    @testset "Pluto extension: Bonds + HTML render contract" begin
        esm = "export default { render({model, el}) {} }"
        w = PlutoWidget(; esm=esm, state=Dict{String,Any}("value" => 0, "min" => 0, "max" => 100))

        # Bonds: the bound variable is the full state Dict; JS values pass through.
        @test AbstractPlutoDingetjes.Bonds.initial_value(w) == w.state
        @test AbstractPlutoDingetjes.Bonds.transform_value(w, Dict("value" => 55)) ==
            Dict("value" => 55)

        # HTML render upholds the @bind contract: imports the runtime, embeds ESM +
        # state, wires a PlutoChannel to the container element. runtime_url was left at
        # its DEFAULT_RUNTIME_URL sentinel, so the render auto-resolves it to the local,
        # offline bundle (cositos-z76.7) -- no separate call needed for the common case.
        html = sprint(show, MIME("text/html"), w)
        @test occursin("document.currentScript.parentElement", html)
        @test occursin("PlutoChannel", html)
        @test occursin("loadWidget", html)
        @test occursin("data:text/javascript;base64,", html)
        @test !occursin(w.runtime_url, html)  # the CDN placeholder itself never appears
        @test occursin("\"value\":0", replace(html, " " => ""))  # state embedded
        @test occursin("render({model, el})", html)                # esm embedded
    end

    @testset "Pluto extension: explicit runtime_url overrides the local-bundle default" begin
        w = PlutoWidget(; esm="export default { render() {} }", state=Dict{String,Any}(),
            runtime_url="https://example.test/front.js")
        html = sprint(show, MIME("text/html"), w)
        @test occursin("https://example.test/front.js", html)
        @test !occursin("data:text/javascript;base64,", html)
    end

    @testset "Pluto extension: local_front_runtime_url bundles @cositos/front with no npm/CDN (cositos-z76.7)" begin
        # Unblocks Pluto without publishing @cositos/front: bundles front/src/*.js (the
        # SAME source the JS test suite certifies, front/test/*.test.js) into one
        # self-contained ESM with no relative imports, as a data: URI — works fully
        # offline, no server, no npm/CDN.
        url = local_front_runtime_url()
        @test startswith(url, "data:text/javascript;base64,")

        encoded = split(url, ","; limit=2)[2]
        bundle = String(base64decode(encoded))

        # Self-contained: no leftover relative import (the one internal edge,
        # model.js -> buffers.js, must be inlined, not referenced). Checks the static
        # `import { ... } from` syntax specifically -- runtime.js's dynamic import(...)
        # calls (loading widget ESM at runtime) and JSDoc prose mentioning "import" are
        # legitimate and must survive untouched.
        @test !occursin("from \"./buffers.js\"", bundle)
        @test !occursin("import {", bundle)

        # Carries every symbol index.js re-exports (the public @cositos/front surface).
        for needle in ["class Model", "class PlutoChannel", "class LocalChannel",
            "class MemoryChannel", "class ClayChannel", "function loadWidget",
            "function renderWidget", "function remove_buffers", "function put_buffers"]
            @test occursin(needle, bundle)
        end

        # A PlutoWidget built with this url embeds it verbatim in the render (same
        # contract as the CDN default, proven above).
        w = PlutoWidget(; esm="export default { render() {} }", state=Dict{String,Any}("value" => 0), runtime_url=url)
        html = sprint(show, MIME("text/html"), w)
        @test occursin(url, html)
    end

    @testset "Pluto batteries-included widget gallery (cositos-z76.7 follow-up)" begin
        # End users shouldn't have to hand-write ESM + a state Dict + PlutoWidget for the
        # six ipywidgets categories docs/widgets.md already certifies (front/test/
        # gallery.test.js). Each Cositos.Pluto function wraps the SAME
        # examples/widgets/*.js this repo already ships and certifies -- no
        # new/reimplemented widget code, only the PlutoWidget construction boilerplate
        # is hidden. Lives in the Cositos.Pluto submodule (not exported from Cositos
        # itself) to avoid clashing with the unrelated top-level int_slider/dropdown
        # real-controls catalog (cositos-70b.7) and with the Pluto.jl tool's own name.

        @testset "Pluto.int_slider" begin
            w = Pluto.int_slider(; value=7, min=1, max=10)
            @test w isa PlutoWidget
            @test w.state == Dict{String,Any}("value" => 7, "min" => 1, "max" => 10)
            @test occursin("input.type = \"range\"", w.esm)
        end

        @testset "Pluto.checkbox" begin
            w = Pluto.checkbox(; value=true)
            @test w.state == Dict{String,Any}("value" => true)
            @test occursin("checkbox", w.esm)
        end

        @testset "Pluto.text" begin
            w = Pluto.text(; value="hi")
            @test w.state == Dict{String,Any}("value" => "hi")
            @test occursin("input.type = \"text\"", w.esm)
        end

        @testset "Pluto.button" begin
            w = Pluto.button(; description="Go")
            @test w.state == Dict{String,Any}("description" => "Go", "clicks" => 0)
            @test occursin("on_click", w.esm)
        end

        @testset "Pluto.dropdown" begin
            w = Pluto.dropdown(["a", "b", "c"]; value="b")
            @test w.state == Dict{String,Any}("options" => ["a", "b", "c"], "value" => "b")
            @test occursin("select", w.esm)
        end

        @testset "Pluto.dropdown defaults value to the first option" begin
            w = Pluto.dropdown([1, 2, 3])
            @test w.state["value"] == "1"
        end

        @testset "Pluto.html" begin
            w = Pluto.html(; value="<b>hi</b>")
            @test w.state == Dict{String,Any}("value" => "<b>hi</b>")
            @test occursin("innerHTML", w.esm)
        end

        @testset "every Cositos.Pluto builder renders via the @bind contract" begin
            for w in [Pluto.int_slider(), Pluto.checkbox(), Pluto.text(), Pluto.button(),
                Pluto.dropdown(["x", "y"]), Pluto.html()]
                html = sprint(show, MIME("text/html"), w)
                @test occursin("PlutoChannel", html)
                @test occursin("data:text/javascript;base64,", html)  # local bundle default
            end
        end

        @testset "kwargs pass through to PlutoWidget (e.g. an explicit runtime_url)" begin
            w = Pluto.checkbox(; value=false, runtime_url="https://example.test/front.js")
            html = sprint(show, MIME("text/html"), w)
            @test occursin("https://example.test/front.js", html)
        end

        @testset "Cositos.Pluto functions are also reachable via selective using" begin
            # `using Cositos.Pluto: int_slider` should work without any Cositos.-level
            # qualification (the alternative call style docs/pluto.md documents).
            w = _pluto_int_slider_selective(; value=3)
            @test w isa PlutoWidget
            @test w.state["value"] == 3
        end
    end

    include("host_tests.jl")
    include("controls_tests.jl")
end
