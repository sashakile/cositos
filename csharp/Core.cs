using System.Text.Json;

namespace Cositos;

// Binding-free anywidget-style backend protocol core (C# port) --- pure logic, no
// kernel/transport code. Builds/parses ipywidgets widget-messaging protocol v2.1.0
// messages, performs binary-buffer split/merge (v2 nested rules), and serializes widget
// state to the Widget State JSON schema v2. Certified against ../fixtures/*.json.
//
// Data model: JSON object = Dictionary<string, object?>; array = List<object?>; binary =
// byte[]; numbers = long or double; plus string/bool/null. buffer_paths are List<object?>
// of segments: string map keys and 0-based long list indices (the wire convention).
public static class Core
{
    public const int ProtocolVersionMajor = 2;
    public const int ProtocolVersionMinor = 1;
    public const string ProtocolVersion = "2.1.0";
    public const string AnywidgetModuleVersion = "~0.11.*";

    // Widget State JSON schema version (distinct from the protocol version 2.1.0).
    public const int StateVersionMajor = 2;
    public const int StateVersionMinor = 0;

    private static Dictionary<string, object?> ImmutableFields(string version) => new()
    {
        ["_model_module"] = "anywidget",
        ["_model_name"] = "AnyModel",
        ["_model_module_version"] = version,
        ["_view_module"] = "anywidget",
        ["_view_name"] = "AnyView",
        ["_view_module_version"] = version,
        ["_view_count"] = null,
    };

    // ---- buffer split / merge (protocol v2 nested rules) ----

    private static bool IsBinary(object? x) => x is byte[];
    private static bool IsContainer(object? x) =>
        x is Dictionary<string, object?> || x is List<object?>;

    private static object? Separate(
        object? sub, List<object?> path, List<List<object?>> paths, List<byte[]> buffers)
    {
        switch (sub)
        {
            case Dictionary<string, object?> obj:
                var outObj = new Dictionary<string, object?>();
                foreach (var (k, v) in obj)
                {
                    var seg = new List<object?>(path) { k };
                    if (IsBinary(v)) { paths.Add(seg); buffers.Add((byte[])v!); }
                    else if (IsContainer(v)) outObj[k] = Separate(v, seg, paths, buffers);
                    else outObj[k] = v;
                }
                return outObj;

            case List<object?> arr:
                var outArr = new List<object?>();
                for (var i = 0; i < arr.Count; i++)
                {
                    var v = arr[i];
                    var seg = new List<object?>(path) { (long)i }; // 0-based wire index
                    if (IsBinary(v)) { outArr.Add(null); paths.Add(seg); buffers.Add((byte[])v!); }
                    else if (IsContainer(v)) outArr.Add(Separate(v, seg, paths, buffers));
                    else outArr.Add(v);
                }
                return outArr;

            default:
                return sub;
        }
    }

    public static (object? Stripped, List<List<object?>> Paths, List<byte[]> Buffers)
        RemoveBuffers(object? state)
    {
        var paths = new List<List<object?>>();
        var buffers = new List<byte[]>();
        var stripped = Separate(state, new List<object?>(), paths, buffers);
        return (stripped, paths, buffers);
    }

    public static object? PutBuffers(object? state, List<List<object?>> paths, List<byte[]> buffers)
    {
        for (var i = 0; i < paths.Count; i++)
            PutOne(state, paths[i], buffers[i]);
        return state;
    }

    private static void PutOne(object? obj, List<object?> path, byte[] buf)
    {
        for (var i = 0; i < path.Count - 1; i++)
            obj = Index(obj, path[i]);
        Assign(obj, path[^1], buf);
    }

    private static object? Index(object? obj, object? key) => key is string s
        ? ((Dictionary<string, object?>)obj!)[s]
        : ((List<object?>)obj!)[(int)Convert.ToInt64(key)];

    private static void Assign(object? obj, object? key, object? value)
    {
        if (key is string s) ((Dictionary<string, object?>)obj!)[s] = value;
        else ((List<object?>)obj!)[(int)Convert.ToInt64(key)] = value;
    }

    // ---- message builders ----

    public static (Dictionary<string, object?> Data, List<byte[]> Buffers, Dictionary<string, object?> Metadata)
        BuildCommOpen(Dictionary<string, object?> state, string anywidgetVersion = AnywidgetModuleVersion)
    {
        var full = ImmutableFields(anywidgetVersion);
        foreach (var (k, v) in state) full[k] = v;
        var (stripped, paths, buffers) = RemoveBuffers(full);
        var data = new Dictionary<string, object?> { ["state"] = stripped, ["buffer_paths"] = PathsToJson(paths) };
        return (data, buffers, new Dictionary<string, object?> { ["version"] = ProtocolVersion });
    }

    public static (Dictionary<string, object?> Data, List<byte[]> Buffers)
        BuildUpdate(Dictionary<string, object?> state)
    {
        var (stripped, paths, buffers) = RemoveBuffers(state);
        var data = new Dictionary<string, object?>
        {
            ["method"] = "update",
            ["state"] = stripped,
            ["buffer_paths"] = PathsToJson(paths),
        };
        return (data, buffers);
    }

    public static Dictionary<string, object?> BuildCustom(object? content) =>
        new() { ["method"] = "custom", ["content"] = content };

    private static List<object?> PathsToJson(List<List<object?>> paths) =>
        paths.Select(p => (object?)new List<object?>(p)).ToList();

    // ---- inbound parsing ----

    public abstract record InboundMessage;
    public sealed record Update(object? State, object? BufferPaths) : InboundMessage;
    public sealed record RequestState : InboundMessage;
    public sealed record Custom(object? Content) : InboundMessage;
    public sealed record Ignored(string? Method) : InboundMessage;

    public static InboundMessage ParseMessage(Dictionary<string, object?> data)
    {
        var method = data.GetValueOrDefault("method") as string;
        return method switch
        {
            "update" => new Update(
                data.GetValueOrDefault("state") ?? new Dictionary<string, object?>(),
                data.GetValueOrDefault("buffer_paths") ?? new List<object?>()),
            "request_state" => new RequestState(),
            "custom" => new Custom(data.GetValueOrDefault("content")),
            // Unknown/missing method is ignored, not thrown (forward-compat, cositos-dow).
            _ => new Ignored(method),
        };
    }

    // ---- serialization: widget-state JSON schema v2 (dump/load) ----

    public static (string ModelId, Dictionary<string, object?> Record) DumpModel(
        (string ModelId, Dictionary<string, object?> State) entry,
        string anywidgetVersion = AnywidgetModuleVersion)
    {
        var (modelId, state) = entry;
        var (stripped, paths, buffers) = RemoveBuffers(state);
        var record = new Dictionary<string, object?>
        {
            ["model_name"] = state.GetValueOrDefault("_model_name") ?? "AnyModel",
            ["model_module"] = state.GetValueOrDefault("_model_module") ?? "anywidget",
            ["model_module_version"] = state.GetValueOrDefault("_model_module_version") ?? anywidgetVersion,
            ["state"] = stripped,
        };
        if (buffers.Count > 0)
        {
            record["buffers"] = paths.Zip(buffers, (p, b) => (object?)new Dictionary<string, object?>
            {
                ["path"] = new List<object?>(p),
                ["encoding"] = "base64",
                ["data"] = Convert.ToBase64String(b),
            }).ToList();
        }
        return (modelId, record);
    }

    public static (string ModelId, object? State) LoadModel((string ModelId, Dictionary<string, object?> Record) item)
    {
        var (modelId, record) = item;
        var state = record["state"];
        var entries = record.GetValueOrDefault("buffers") as List<object?> ?? new List<object?>();
        var paths = new List<List<object?>>();
        var buffers = new List<byte[]>();
        foreach (var e in entries.Cast<Dictionary<string, object?>>())
        {
            paths.Add(new List<object?>((List<object?>)e["path"]!));
            buffers.Add(DecodeBuffer(e));
        }
        return (modelId, PutBuffers(state, paths, buffers));
    }

    private static byte[] DecodeBuffer(Dictionary<string, object?> entry)
    {
        if (entry.GetValueOrDefault("encoding") as string != "base64")
            throw new ArgumentException(
                $"Unsupported buffer encoding: {entry.GetValueOrDefault("encoding") ?? "null"} (expected 'base64')");
        return Convert.FromBase64String((string)entry["data"]!);
    }

    public static Dictionary<string, object?> DumpDocument(
        IEnumerable<(string ModelId, Dictionary<string, object?> State)> entries,
        string anywidgetVersion = AnywidgetModuleVersion)
    {
        var state = new Dictionary<string, object?>();
        foreach (var entry in entries)
        {
            var (modelId, record) = DumpModel(entry, anywidgetVersion);
            if (string.IsNullOrEmpty(modelId))
                throw new ArgumentException("model_id must be a non-empty string (it is the document key)");
            if (state.ContainsKey(modelId))
                throw new ArgumentException($"duplicate model_id {modelId}: document keys must be unique");
            state[modelId] = record;
        }
        return new Dictionary<string, object?>
        {
            ["version_major"] = (long)StateVersionMajor,
            ["version_minor"] = (long)StateVersionMinor,
            ["state"] = state,
        };
    }

    public static List<(string ModelId, object? State)> LoadDocument(Dictionary<string, object?> doc)
    {
        var state = (Dictionary<string, object?>)doc["state"]!;
        return state.Select(kv => LoadModel((kv.Key, (Dictionary<string, object?>)kv.Value!))).ToList();
    }

    // ---- JSON interop (parse fixtures into the object model above) ----

    public static object? FromJson(string json)
    {
        using var doc = JsonDocument.Parse(json);
        return Convert_(doc.RootElement);
    }

    private static object? Convert_(JsonElement e) => e.ValueKind switch
    {
        JsonValueKind.Object => e.EnumerateObject()
            .ToDictionary(p => p.Name, p => Convert_(p.Value)),
        JsonValueKind.Array => e.EnumerateArray().Select(Convert_).ToList(),
        JsonValueKind.String => e.GetString(),
        JsonValueKind.Number => e.TryGetInt64(out var l) ? l : e.GetDouble(),
        JsonValueKind.True => true,
        JsonValueKind.False => false,
        _ => null,
    };
}
