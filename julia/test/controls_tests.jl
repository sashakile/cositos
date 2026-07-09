# Julia port of ../../tests/test_contrib_controls.py — proves the real-controls catalog
# builder (cositos-70b.2) is genuinely cross-language: same fixtures/controls-catalog.json
# (not a re-derived copy), same id-uniqueness rule, same three verification tiers (fixture
# round-trip, static-render view-identity, live-comm-open payload) as the Python builder.
# Requires JSON to be loaded (CositosControlsExt); runtests.jl already `using JSON`.

by_id(entries) = Dict(entries)

@testset "controls catalog builder (cositos-70b.7)" begin
    @testset "int_slider carries the real controls identity" begin
        entries = int_slider()
        _, state = entries[1]
        @test state["_model_name"] == "IntSliderModel"
        @test state["_model_module"] == "@jupyter-widgets/controls"
        @test state["_model_module_version"] == "2.0.0"
        @test state["_view_name"] == "IntSliderView"
        @test state["_view_module"] == "@jupyter-widgets/controls"
        @test state["_view_module_version"] == "2.0.0"
    end

    @testset "int_slider applies overrides over the catalog defaults" begin
        entries = int_slider(; value=7, min=1, max=10)
        _, state = entries[1]
        @test state["value"] == 7
        @test state["min"] == 1
        @test state["max"] == 10
        @test state["step"] == 1
        @test state["continuous_update"] == true
    end

    @testset "int_slider references freshly minted companion models" begin
        entries = int_slider()
        ids = by_id(entries)
        _, state = entries[1]

        style_ref = state["style"]
        layout_ref = state["layout"]
        @test startswith(style_ref, "IPY_MODEL_")
        @test startswith(layout_ref, "IPY_MODEL_")

        style_id = replace(style_ref, "IPY_MODEL_" => "")
        layout_id = replace(layout_ref, "IPY_MODEL_" => "")
        @test haskey(ids, style_id)
        @test haskey(ids, layout_id)
        @test ids[style_id]["_model_name"] == "SliderStyleModel"
        @test ids[style_id]["_view_name"] === nothing
        @test ids[layout_id]["_model_name"] == "LayoutModel"
        @test ids[layout_id]["_model_module"] == "@jupyter-widgets/base"
    end

    @testset "two int_slider calls never share a companion model id" begin
        a = int_slider(; value=1)
        b = int_slider(; value=2)
        a_ids = Set(mid for (mid, _) in a)
        b_ids = Set(mid for (mid, _) in b)
        @test isempty(intersect(a_ids, b_ids))

        doc = dump_document(vcat(a, b))
        @test length(doc["state"]) == length(a) + length(b)
    end

    @testset "dropdown carries options and the description_style companion" begin
        entries = dropdown(["a", "b", "c"]; value="b")
        ids = by_id(entries)
        _, state = entries[1]

        @test state["_model_name"] == "DropdownModel"
        @test state["_options_labels"] == ["a", "b", "c"]
        @test state["index"] == 1  # 0-based wire index for "b"

        style_id = replace(state["style"], "IPY_MODEL_" => "")
        @test ids[style_id]["_model_name"] == "DescriptionStyleModel"
    end

    @testset "dropdown with no matching value leaves index unselected" begin
        entries = dropdown(["a", "b"]; value="not-there")
        _, state = entries[1]
        @test state["index"] === nothing
    end

    @testset "dropdown index override bypasses the value lookup" begin
        entries = dropdown(["a", "b", "c"]; index=2)
        _, state = entries[1]
        @test state["index"] == 2
    end

    @testset "vbox composes children by reference" begin
        slider_entries = int_slider(; value=5)
        dropdown_entries = dropdown([1, 2]; value=1)

        entries = vbox([slider_entries, dropdown_entries])
        _, state = entries[1]

        @test state["_model_name"] == "VBoxModel"
        slider_root_id = slider_entries[1][1]
        dropdown_root_id = dropdown_entries[1][1]
        @test state["children"] == ["IPY_MODEL_$(slider_root_id)", "IPY_MODEL_$(dropdown_root_id)"]

        ids = by_id(entries)
        @test haskey(ids, slider_root_id)
        @test haskey(ids, dropdown_root_id)
    end

    @testset "hbox composes children by reference" begin
        a = int_slider(; value=1)
        b = int_slider(; value=2)
        entries = hbox([a, b])
        _, state = entries[1]
        @test state["_model_name"] == "HBoxModel"
        @test length(state["children"]) == 2
    end

    @testset "tier 1: fixture round-trip via dump_document/load_document" begin
        entries = vbox([int_slider(; value=3), dropdown(["x", "y"]; value="x")])
        doc = dump_document(entries)
        reloaded = load_document(doc)
        @test Set(mid for (mid, _) in reloaded) == Set(mid for (mid, _) in entries)
        redumped = dump_document(reloaded)
        @test jsonequal(redumped, doc)
    end

    @testset "tier 2: static-render — with_view_identity preserves the real controls view identity" begin
        # Parity with the Python builder's embed_html check (cositos-70b.2 AC #2): a real
        # controls model's OWN view identity must survive static-render enrichment
        # untouched — host-set state wins over with_view_identity's anywidget defaults, so
        # the CDN html-manager renders the real view class, not a broken anywidget fallback
        # (cositos-mx7 lineage). Julia has no embed_html host yet, so this checks the same
        # enrichment function the future host would call.
        entries = vbox([int_slider(; value=5)])
        doc = dump_document(entries)
        enriched = with_view_identity(doc)

        vbox_id = entries[1][1]
        vbox_state = enriched["state"][vbox_id]["state"]
        @test vbox_state["_view_name"] == "VBoxView"
        @test vbox_state["_view_module"] == "@jupyter-widgets/controls"

        slider_id = replace(vbox_state["children"][1], "IPY_MODEL_" => "")
        slider_state = enriched["state"][slider_id]["state"]
        @test slider_state["_view_name"] == "IntSliderView"
        @test slider_state["value"] == 5
    end

    @testset "tier 3: live-comm-open payload carries the real controls identity" begin
        # Parity with the Python builder's live-kernel check (cositos-70b.2 AC #3): the
        # payload build_comm_open()/Widget.open! would actually send to a live IJulia
        # comm carries the real @jupyter-widgets identity end to end — not just the
        # in-memory ModelEntry. The IJulia transport itself is already live-certified
        # (cositos-z76.6/.8, cositos-059.2/.3); this proves the NEW builder's output
        # survives that exact seam (build_comm_open), matching host_tests.jl's
        # FakeTransport convention for the Widget façade.
        entries = int_slider(; value=42)
        _, state = entries[1]
        data, _buffers, _metadata = build_comm_open(state)
        @test data["state"]["_model_name"] == "IntSliderModel"
        @test data["state"]["_model_module"] == "@jupyter-widgets/controls"
        @test data["state"]["value"] == 42

        t = FakeTransport()
        w = Widget(t; get_state=() -> state, model_id=entries[1][1])
        open!(w)
        _msg_type, content, _b, _m = t.sent[1]
        @test content["state"]["_model_name"] == "IntSliderModel"
        @test content["state"]["_view_name"] == "IntSliderView"
    end

    @testset "repeated calls mint distinct widget ids even with identical overrides" begin
        first = int_slider(; value=1)
        second = int_slider(; value=1)
        @test first[1][1] != second[1][1]

        first_d = dropdown([1]; value=1)
        second_d = dropdown([1]; value=1)
        @test first_d[1][1] != second_d[1][1]
    end
end
