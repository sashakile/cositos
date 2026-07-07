# Widget façade tests against an in-memory fake transport.
# Julia analogue of ../../tests/test_model.py — certifies the kernel-agnostic Widget
# façade (open/send_state/inbound dispatch/close) independent of any live kernel.

"An in-memory transport that records sent messages and can inject inbound ones."
mutable struct FakeTransport
    sent::Vector{Any}
    cb::Union{Function,Nothing}
    receive::Bool
    cid::String
end
FakeTransport(; receive::Bool=true, cid::AbstractString="") =
    FakeTransport(Any[], nothing, receive, String(cid))

Cositos.supports_receive(t::FakeTransport) = t.receive
Cositos.comm_id(t::FakeTransport) = t.cid
function Cositos.transport_send(t::FakeTransport, msg_type, content; buffers=Any[], metadata=nothing)
    push!(t.sent, (msg_type, content, buffers, metadata))
    return nothing
end
Cositos.transport_on_message(t::FakeTransport, cb) = (t.cb = cb; nothing)
deliver!(t::FakeTransport, data; buffers=Any[]) = t.cb(data, buffers)

function make_widget(initial)
    store = Dict{String,Any}(initial)
    t = FakeTransport()
    w = Widget(t; get_state=() -> copy(store), set_state=(d) -> merge!(store, d), model_id="m1")
    return w, t, store
end

@testset "Widget façade (fake transport)" begin
    @testset "open! sends comm_open with protocol metadata + model identity" begin
        w, t, _ = make_widget(Dict("_esm" => "x", "value" => 0))
        open!(w)
        msg_type, content, _buffers, metadata = t.sent[1]
        @test msg_type == "comm_open"
        @test metadata == Dict{String,Any}("version" => "2.1.0")
        @test content["state"]["_model_name"] == "AnyModel"
    end

    @testset "send_state! emits an update with current state" begin
        w, t, store = make_widget(Dict("value" => 0))
        open!(w)
        store["value"] = 7
        send_state!(w)
        msg_type, content, _b, _m = t.sent[end]
        @test msg_type == "comm_msg"
        @test content["method"] == "update"
        @test content["state"]["value"] == 7
    end

    @testset "inbound update applies state" begin
        w, t, store = make_widget(Dict("value" => 0))
        open!(w)
        deliver!(t, Dict("method" => "update", "state" => Dict("value" => 99), "buffer_paths" => []))
        @test store["value"] == 99
    end

    @testset "inbound unknown/missing method is ignored, never throws" begin
        w, t, store = make_widget(Dict("value" => 7))
        open!(w)
        deliver!(t, Dict("method" => "echo_update", "state" => Dict("value" => 99)))
        deliver!(t, Dict("method" => "bogus"))
        deliver!(t, Dict{String,Any}())
        @test store["value"] == 7
    end

    @testset "request_state triggers a full update" begin
        w, t, _ = make_widget(Dict("value" => 5))
        open!(w)
        deliver!(t, Dict("method" => "request_state"))
        msg_type, content, _b, _m = t.sent[end]
        @test msg_type == "comm_msg"
        @test content["state"]["value"] == 5
    end

    @testset "inbound update merges buffers" begin
        w, t, store = make_widget(Dict("img" => nothing))
        open!(w)
        deliver!(t, Dict("method" => "update", "state" => Dict{String,Any}(), "buffer_paths" => Any[["img"]]);
            buffers=Any[Vector{UInt8}("PNG")])
        @test store["img"] == Vector{UInt8}("PNG")
    end

    @testset "send_custom! emits a custom message" begin
        w, t, _ = make_widget(Dict("value" => 0))
        open!(w)
        send_custom!(w, Dict("kind" => "ping"))
        msg_type, content, _b, _m = t.sent[end]
        @test msg_type == "comm_msg"
        @test content == Dict{String,Any}("method" => "custom", "content" => Dict("kind" => "ping"))
    end

    @testset "inbound custom invokes the callback with content + buffers" begin
        received = Any[]
        t = FakeTransport()
        w = Widget(t; get_state=() -> Dict{String,Any}(), on_custom=(c, b) -> push!(received, (c, b)))
        open!(w)
        deliver!(t, Dict("method" => "custom", "content" => Dict("kind" => "pong")); buffers=Any[Vector{UInt8}("x")])
        @test received == [(Dict("kind" => "pong"), Any[Vector{UInt8}("x")])]
    end

    @testset "inbound update without set_state is a no-op" begin
        t = FakeTransport()
        w = Widget(t; get_state=() -> Dict{String,Any}("value" => 0))  # no set_state
        open!(w)
        deliver!(t, Dict("method" => "update", "state" => Dict("value" => 1), "buffer_paths" => []))
        deliver!(t, Dict("method" => "custom", "content" => 1))  # no on_custom either
    end

    @testset "send_state! with include filters keys" begin
        w, t, _ = make_widget(Dict("a" => 1, "b" => 2, "_esm" => "x"))
        open!(w)
        send_state!(w; include=Set(["a"]))
        _mt, content, _b, _m = t.sent[end]
        @test content["state"] == Dict{String,Any}("a" => 1)
    end

    @testset "mimebundle includes repr text" begin
        w, _t, _ = make_widget(Dict("value" => 0))
        bundle = mimebundle(w, "Counter(value=0)")
        @test bundle["text/plain"] == "Counter(value=0)"
    end

    @testset "close! sends comm_close once (idempotent)" begin
        w, t, _ = make_widget(Dict("value" => 0))
        open!(w)
        close!(w)
        @test t.sent[end][1] == "comm_close"
        n = length(t.sent)
        close!(w)
        @test length(t.sent) == n
    end

    @testset "open! is idempotent (no duplicate comm_open)" begin
        w, t, _ = make_widget(Dict("_esm" => "x", "value" => 0))
        open!(w)
        n = length(t.sent)
        open!(w)
        @test length(t.sent) == n
    end

    @testset "send_state! before open! raises a clear error" begin
        w, _t, _ = make_widget(Dict("value" => 0))
        err = try
            send_state!(w)
            nothing
        catch e
            e
        end
        @test err isa ErrorException
        @test occursin("open", lowercase(err.msg))
    end

    @testset "open! adopts the transport's server-generated comm id" begin
        store = Dict{String,Any}("_esm" => "x", "value" => 0)
        t = FakeTransport(; cid="server-generated-id")
        w = Widget(t; get_state=() -> copy(store), model_id="ignored")
        open!(w)
        @test w.model_id == "server-generated-id"
    end

    @testset "open! keeps model_id when transport has no comm id" begin
        w, _t, _ = make_widget(Dict("value" => 0))  # FakeTransport default cid=""
        open!(w)
        @test w.model_id == "m1"
    end

    @testset "broadcast-only transport opens but registers no inbound handler" begin
        t = FakeTransport(; receive=false)
        w = Widget(t; get_state=() -> Dict{String,Any}("value" => 1), set_state=(d) -> nothing, model_id="m1")
        open!(w)
        @test t.sent[1][1] == "comm_open"
        @test t.cb === nothing
    end
end
