using Test
using Base64
using JSON
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
end
