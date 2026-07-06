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
ExpectThrows(() => Core.ParseMessage(Obj(("method", "bogus"))), "parse rejects unknown method");

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

Console.WriteLine($"\nRan {count} checks, {failures} failures.");
return failures > 0 ? 1 : 0;
