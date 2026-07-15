// Fixture-conformance tests for the C# protocol core. Dependency-free: System.Text.Json
// + Convert from the shared framework, no NuGet. Run:  dotnet run   (or: mise run csharp-test)
using Cositos;

const string FixturesDir = "../fixtures";
int failures = 0, count = 0;

Dictionary<string, object?> LoadFixture(string name) =>
    (Dictionary<string, object?>)Core.FromJson(File.ReadAllText($"{FixturesDir}/{name}.json"))!;

void Check(bool cond, string msg)
{
    count++;
    if (!cond) { failures++; Console.WriteLine($"  FAIL: {msg}"); }
}

void ExpectThrows(Action a, string msg)
{
    try { a(); Check(false, msg); } catch { Check(true, msg); }
}

static bool IsNum(object? x) => x is long or int or double;
static double ToD(object? x) => Convert.ToDouble(x);

bool JsonEqual(object? a, object? b)
{
    if (a is Dictionary<string, object?> da && b is Dictionary<string, object?> db)
    {
        if (da.Count != db.Count) return false;
        foreach (var (k, v) in da)
            if (!db.TryGetValue(k, out var vb) || !JsonEqual(v, vb)) return false;
        return true;
    }
    if (a is List<object?> la && b is List<object?> lb)
    {
        if (la.Count != lb.Count) return false;
        for (var i = 0; i < la.Count; i++) if (!JsonEqual(la[i], lb[i])) return false;
        return true;
    }
    if (a is null && b is null) return true;
    if (a is null || b is null) return false;
    if (IsNum(a) && IsNum(b)) return ToD(a) == ToD(b);
    return a.Equals(b);
}

List<object?> B64(List<byte[]> buffers) =>
    buffers.Select(b => (object?)Convert.ToBase64String(b)).ToList();

static byte[] F32(params double[] xs)
{
    var bytes = new List<byte>();
    foreach (var x in xs) bytes.AddRange(BitConverter.GetBytes((float)x));
    return bytes.ToArray();
}

Dictionary<string, object?> Obj(params (string, object?)[] kvs)
{
    var d = new Dictionary<string, object?>();
    foreach (var (k, v) in kvs) d[k] = v;
    return d;
}

List<object?> Arr(params object?[] xs) => new(xs);

// ---- message-builder conformance ----
{
    var fx = LoadFixture("comm_open");
    var (data, buffers, metadata) = Core.BuildCommOpen(
        Obj(("_esm", "export default { render() {} }"), ("value", 0L)));
    Check(JsonEqual(fx["data"], data), "comm_open data matches fixture");
    Check(JsonEqual(fx["buffers_b64"], B64(buffers)), "comm_open buffers match");
    Check(JsonEqual(fx["metadata"], metadata), "comm_open metadata matches fixture");
}
{
    var fx = LoadFixture("update");
    var (data, buffers) = Core.BuildUpdate(Obj(("value", 42L)));
    Check(JsonEqual(fx["data"], data), "update data matches fixture");
    Check(JsonEqual(fx["buffers_b64"], B64(buffers)), "update has no buffers");
}
{
    var fx = LoadFixture("update_nested_buffer");
    var (data, buffers) = Core.BuildUpdate(Obj(
        ("img", Obj(("bytes", "PNGDATA"u8.ToArray()))),
        ("shape", Arr(1L, 1L))));
    Check(JsonEqual(fx["data"], data), "update_nested_buffer data matches fixture");
    Check(JsonEqual(fx["buffers_b64"], B64(buffers)), "update_nested_buffer buffers match");
}
{
    var fx = LoadFixture("custom");
    Check(JsonEqual(fx["data"], Core.BuildCustom(Obj(("event", "click"), ("n", 3L)))),
        "custom matches fixture");
}

// ---- inbound parsing ----
Check(Core.ParseMessage(Obj(("method", "update"), ("state", Obj(("a", 1L))), ("buffer_paths", Arr())))
        is Core.Update, "parse update");
Check(Core.ParseMessage(Obj(("method", "request_state"))) is Core.RequestState, "parse request_state");
Check(Core.ParseMessage(Obj(("method", "custom"), ("content", 42L))) is Core.Custom { Content: 42L },
    "parse custom");
Check(Core.ParseMessage(Obj(("method", "bogus"))) is Core.Ignored { Method: "bogus" },
    "parse ignores unknown method");
Check(Core.ParseMessage(Obj()) is Core.Ignored { Method: null }, "parse ignores missing method");

// ---- buffer split / merge ----
{
    var blob = "AB"u8.ToArray();
    var (stripped, paths, buffers) = Core.RemoveBuffers(
        Obj(("n", 1L), ("x", Obj(("ar", blob))), ("xs", Arr(blob, 2L))));
    Check(JsonEqual(stripped, Obj(("n", 1L), ("x", Obj()), ("xs", Arr(null, 2L)))), "buffers stripped shape");
    Check(JsonEqual(paths.Select(p => (object?)new List<object?>(p)).ToList(), Arr(Arr("x", "ar"), Arr("xs", 0L))), "buffer paths 0-based");
    var restored = (Dictionary<string, object?>)Core.PutBuffers(stripped, paths, buffers)!;
    Check(((byte[])((Dictionary<string, object?>)restored["x"]!)["ar"]!).SequenceEqual(blob), "restored map buffer");
    Check(((byte[])((List<object?>)restored["xs"]!)[0]!).SequenceEqual(blob), "restored list-slot buffer");
}

// ---- serialization: dump/load_document vs widget-state.json ----
(string, Dictionary<string, object?>)[] WidgetStateEntries() => new[]
{
    ("box", Obj(("_esm", "export default { render({model, el}) { /* VBox */ } }"),
                ("children", Arr("IPY_MODEL_plot")))),
    ("plot", Obj(("_esm", "export default { render({model, el}) { /* float32 plot */ } }"),
                 ("shape", Arr(3L)), ("dtype", "float32"), ("data", F32(1.5, 2.5, -3.0)))),
};
{
    var fx = LoadFixture("widget-state");
    Check(JsonEqual(fx, Core.DumpDocument(WidgetStateEntries())), "dump_document reproduces fixture");
}
{
    var (_, record) = Core.DumpModel(("plot", Obj(
        ("_esm", "e"), ("shape", Arr(3L)), ("dtype", "float32"), ("data", F32(1.5, 2.5, -3.0)))));
    var buf = (Dictionary<string, object?>)((List<object?>)record["buffers"]!)[0]!;
    Check(JsonEqual(buf["path"], Arr("data")), "buffer record path");
    Check((string)buf["encoding"]! == "base64", "buffer record encoding");
    Check((string)buf["data"]! == "AADAPwAAIEAAAEDA", "buffer record base64 matches fixture");
}
{
    var loaded = Core.LoadDocument(LoadFixture("widget-state"));
    var byId = loaded.ToDictionary(e => e.ModelId, e => (Dictionary<string, object?>)e.State!);
    Check(loaded.Select(e => e.ModelId).OrderBy(x => x).SequenceEqual(new[] { "box", "plot" }), "load ids");
    Check(JsonEqual(byId["box"]["children"], Arr("IPY_MODEL_plot")), "composition ref survives");
    Check(((byte[])byId["plot"]["data"]!).SequenceEqual(F32(1.5, 2.5, -3.0)), "float32 buffer raw bytes");
}
{
    var entries = new[]
    {
        ("box", Obj(("children", Arr("IPY_MODEL_child")))),
        ("child", Obj(("value", 42L))),
    };
    var doc = Core.DumpDocument(entries);
    Check(JsonEqual(doc, Core.DumpDocument(
        Core.LoadDocument(doc).Select(e => (e.ModelId, (Dictionary<string, object?>)e.State!)))),
        "buffer-free round-trip law");
}
ExpectThrows(() => Core.DumpDocument(new[] { ("", Obj(("value", 1L))) }), "reject empty model_id");
ExpectThrows(() => Core.DumpDocument(new[] { ("dup", Obj(("value", 1L))), ("dup", Obj(("value", 2L))) }),
    "reject duplicate model_id");
ExpectThrows(() => Core.LoadModel(("m", Obj(
    ("state", Obj(("data", null))),
    ("buffers", Arr(Obj(("path", Arr("data")), ("encoding", "hex"), ("data", "00"))))))),
    "reject non-base64 encoding");

// ---- buffer-split edge cases: cycle detection and depth capping ----
{
    // Self-referential container must raise a clear error, not stack-overflow.
    var state = new Dictionary<string, object?>();
    state["a"] = 1L;
    state["self"] = state;
    ExpectThrows(() => Core.RemoveBuffers(state), "cycle detection raises InvalidOperationException");
}
{
    // Deep nesting must raise a clear error naming the depth.
    Dictionary<string, object?> state = new();
    var node = state;
    for (var i = 0; i < 2000; i++)
    {
        var child = new Dictionary<string, object?>();
        node["n"] = child;
        node = child;
    }
    ExpectThrows(() => Core.RemoveBuffers(state), "depth capping raises InvalidOperationException");
}
{
    // Shared acyclic subtrees (DAG) is fine — not a cycle.
    var shared = new Dictionary<string, object?> { ["v"] = 1L };
    var state = new Dictionary<string, object?> { ["a"] = shared, ["b"] = shared };
    var (stripped, _, _) = Core.RemoveBuffers(state);
    Check(JsonEqual(stripped, Obj(("a", Obj(("v", 1L))), ("b", Obj(("v", 1L))))), "DAG is not misreported as cycle");
}

// ---- lifecycle reducer fixture certification ----
Phase PhaseFromStr(string s) => s switch
{
    "unopened" => Phase.Unopened,
    "open" => Phase.Open,
    "closed" => Phase.Closed,
    _ => throw new ArgumentException($"unknown phase: {s}"),
};

object? EventFromDict(Dictionary<string, object?> d) => ((string)d["kind"]) switch
{
    "open" => new Open(),
    "send_state" => new SendState(
        d.TryGetValue("include", out var incl) ? new HashSet<string>(((List<object?>)incl!).Cast<string>()) : null),
    "send_custom" => new SendCustom(d.GetValueOrDefault("content"),
        d.TryGetValue("buffers", out var bufs) ? (List<object?>?)bufs : null),
    "inbound" => new Inbound((Dictionary<string, object?>)d["message"]!,
        d.TryGetValue("buffers", out var bufs2) ? (List<object?>?)bufs2 : null),
    "close" => new Close(),
    "comm_id_assigned" => new CommIdAssigned((string)d["id"]!),
    _ => throw new ArgumentException($"unknown event kind: {d["kind"]}"),
};

{
    var lifecycleDir = $"{FixturesDir}/lifecycle";
    foreach (var fxFile in Directory.GetFiles(lifecycleDir, "*.json"))
    {
        var fxName = Path.GetFileName(fxFile);
        var entries = (List<object?>)Core.FromJson(File.ReadAllText(fxFile))!;
        foreach (var rawEntry in entries)
        {
            var entry = (List<object?>)rawEntry!;
            var phaseInStr = (string)entry[0]!;
            var evDict = (Dictionary<string, object?>)entry[1]!;
            var stateIn = (Dictionary<string, object?>)entry[2]!;
            var phaseOutStr = (string)entry[3]!;
            var fxEffects = (List<object?>)entry[4]!;
            var caps = entry.Count >= 6 ? (Dictionary<string, object?>)entry[5]! : new Dictionary<string, object?>();

            var phaseIn = PhaseFromStr(phaseInStr);
            var ev = EventFromDict(evDict);
            var capabilities = new TransportCapabilities(
                SupportsReceive: caps.TryGetValue("supports_receive", out var sr) ? (bool)sr : true,
                SupportsRequestState: caps.TryGetValue("supports_request_state", out var rs) ? (bool)rs : true,
                SupportsCustom: caps.TryGetValue("supports_custom", out var sc) ? (bool)sc : true,
                SupportsBuffers: caps.TryGetValue("supports_buffers", out var sb) ? (bool)sb : true
            );

            var (phaseOut, effects) = Lifecycle.Reduce(phaseIn, ev, stateIn, capabilities);

            Check(phaseOut == PhaseFromStr(phaseOutStr), $"{fxName}: phase {phaseInStr} -> {phaseOutStr}");
            Check(effects.Count == fxEffects.Count, $"{fxName}: effect count {effects.Count} == {fxEffects.Count}");

            for (int i = 0; i < Math.Min(effects.Count, fxEffects.Count); i++)
            {
                var fe = (Dictionary<string, object?>)fxEffects[i]!;
                var kind = (string)fe["kind"]!;
                bool kindOk = kind switch
                {
                    "send" => effects[i] is Send s && (!fe.TryGetValue("msg_type", out var mt) || (string)mt! == s.MsgType),
                    "listen" => effects[i] is Listen,
                    "apply_state" => effects[i] is ApplyState,
                    "invoke_custom" => effects[i] is InvokeCustom,
                    "error" => effects[i] is Error,
                    _ => false,
                };
                Check(kindOk, $"{fxName}: effect[{i}] kind={kind}");
            }
        }
    }
}

Console.WriteLine($"\nRan {count} checks, {failures} failures.");
return failures > 0 ? 1 : 0;
