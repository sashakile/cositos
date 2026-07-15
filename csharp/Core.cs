using System.Text.Json;

namespace Cositos;

// ---- lifecycle types ----

/// <summary>The three phases of a widget's lifecycle.</summary>
public enum Phase { Unopened, Open, Closed }

/// <summary>Declares which event kinds the transport can carry.</summary>
public record TransportCapabilities(
    bool SupportsReceive = true,
    bool SupportsRequestState = true,
    bool SupportsCustom = true,
    bool SupportsBuffers = true
);

// Effect types
public record Send(string MsgType, Dictionary<string, object?> Data,
    List<object?>? Buffers = null, Dictionary<string, object?>? Metadata = null);
public record Listen();
public record ApplyState(Dictionary<string, object?> State);
public record InvokeCustom(object? Content, List<object?>? Buffers = null);
public record Error(string Message);

// Event types
public record Open();
public record SendState(HashSet<string>? Include = null);
public record SendCustom(object? Content, List<object?>? Buffers = null);
public record Inbound(Dictionary<string, object?> Message, List<object?>? Buffers = null);
public record Close();
public record CommIdAssigned(string Id);

// ---- lifecycle reducer ----
public static class Lifecycle
{
    /// <summary>
    /// Pure widget lifecycle reducer. Encodes the widget lifecycle as a deterministic
    /// state machine with three phases, six event types, and five effect types.
    /// No I/O, no side effects — the shell walks the returned effects.
    /// </summary>
    /// <param name="phase">Current widget phase.</param>
    /// <param name="ev">The event to process (Open, SendState, SendCustom, Inbound, Close, or CommIdAssigned).</param>
    /// <param name="currentState">Current host widget state dict.</param>
    /// <param name="capabilities">Transport capability flags.</param>
    /// <returns>(newPhase, effects) tuple.</returns>
    public static (Phase NewPhase, List<object?> Effects) Reduce(
        Phase phase, object? ev, Dictionary<string, object?> currentState,
        TransportCapabilities capabilities)
    {
        if (ev is Open) return ReduceOpen(phase, currentState, capabilities);
        if (ev is SendState ss) return ReduceSendState(phase, ss, currentState, capabilities);
        if (ev is SendCustom sc) return ReduceSendCustom(phase, sc, capabilities);
        if (ev is Inbound ib) return ReduceInbound(phase, ib, currentState, capabilities);
        if (ev is Close) return ReduceClose(phase);
        if (ev is CommIdAssigned) return (Phase.Open, new List<object?>());
        return (phase, new List<object?> { new Error($"unknown event type: {ev?.GetType().Name ?? "null"}") });
    }

    /// <summary>Handle an Open event — transition to Open phase, send comm_open (+ listen if supported).</summary>
    private static (Phase, List<object?>) ReduceOpen(
        Phase phase, Dictionary<string, object?> currentState,
        TransportCapabilities capabilities)
    {
        if (phase == Phase.Unopened || phase == Phase.Closed)
        {
            var full = Core.ImmutableFields();
            foreach (var (k, v) in currentState) full[k] = v;
            var (data, buffers, metadata) = Core.BuildCommOpen(full);
            var effects = new List<object?> { new Send("comm_open", data, buffers.Cast<object?>().ToList(), metadata) };
            if (capabilities.SupportsReceive)
                effects.Add(new Listen());
            return (Phase.Open, effects);
        }
        // Idempotent: already open, no-op
        return (Phase.Open, new List<object?>());
    }

    /// <summary>Handle a SendState event — send an update (full with identity re-merge, or filtered).</summary>
    private static (Phase, List<object?>) ReduceSendState(
        Phase phase, SendState ev, Dictionary<string, object?> currentState,
        TransportCapabilities capabilities)
    {
        if (phase != Phase.Open)
            return (phase, new List<object?> { new Error("send_state() requires an open comm; call open() first") });
        Dictionary<string, object?> state;
        if (ev.Include == null)
        {
            state = Core.ImmutableFields();
            foreach (var (k, v) in currentState) state[k] = v;
        }
        else
        {
            state = new Dictionary<string, object?>();
            foreach (var (k, v) in currentState)
                if (ev.Include.Contains(k)) state[k] = v;
        }
        var (data, buffers) = Core.BuildUpdate(state);
        return (phase, new List<object?> { new Send("comm_msg", data, buffers.Cast<object?>().ToList()) });
    }

    /// <summary>Handle a SendCustom event — send a custom message (checks transport capabilities).</summary>
    private static (Phase, List<object?>) ReduceSendCustom(
        Phase phase, SendCustom ev, TransportCapabilities capabilities)
    {
        if (phase != Phase.Open)
            return (phase, new List<object?> { new Error("send_custom() requires an open comm; call open() first") });
        if (!capabilities.SupportsCustom)
            return (phase, new List<object?> { new Error("custom messages are not supported by this transport") });
        if (!capabilities.SupportsBuffers && (ev.Buffers?.Count > 0))
            return (phase, new List<object?> { new Error("buffers are not supported by this transport") });
        return (phase, new List<object?> { new Send("comm_msg", Core.BuildCustom(ev.Content), ev.Buffers?.Cast<object?>().ToList() ?? new List<object?>()) });
    }

    /// <summary>Handle an Inbound event — dispatch to update/request_state/custom/ignored based on message type.</summary>
    private static (Phase, List<object?>) ReduceInbound(
        Phase phase, Inbound ev, Dictionary<string, object?> currentState,
        TransportCapabilities capabilities)
    {
        if (phase != Phase.Open)
            return (phase, new List<object?>());

        var message = Core.ParseMessage(ev.Message);
        switch (message)
        {
            case Core.Update upd:
                var state = new Dictionary<string, object?>((Dictionary<string, object?>)upd.State!);
                Core.PutBuffers(state, upd.BufferPaths, ev.Buffers?.Cast<byte[]>().ToList()!);
                return (phase, new List<object?> { new ApplyState(state) });

            case Core.RequestState:
                if (!capabilities.SupportsRequestState)
                    return (phase, new List<object?>());
                return ReduceSendState(phase, new SendState(), currentState, capabilities);

            case Core.Custom cust:
                return (phase, new List<object?> { new InvokeCustom(cust.Content, ev.Buffers) });

            default:
                return (phase, new List<object?>());
        }
    }

    /// <summary>Handle a Close event — transition to Closed phase, send comm_close.</summary>
    private static (Phase, List<object?>) ReduceClose(Phase phase)
    {
        if (phase == Phase.Open)
            return (Phase.Closed, new List<object?> { new Send("comm_close", new Dictionary<string, object?>()) });
        return (phase, new List<object?>());
    }
}

// ---- imperative shell ----

/// <summary>
/// Thin imperative shell that calls Lifecycle.Reduce and executes effects.
/// Replaces the old Widget lifecycle logic. The shell owns the event loop.
/// </summary>
public class WidgetShell
{
    public object Transport { get; }
    public Func<Dictionary<string, object?>> GetState { get; }
    public Action<Dictionary<string, object?>>? SetState { get; }
    public Action<object?, List<object?>?>? OnCustom { get; }
    public string ModelId { get; set; }
    public Phase Phase { get; private set; }
    public TransportCapabilities Capabilities { get; }
    private bool _listening;

    public WidgetShell(
        object transport,
        Func<Dictionary<string, object?>> getState,
        Action<Dictionary<string, object?>>? setState = null,
        string modelId = "",
        Action<object?, List<object?>?>? onCustom = null,
        TransportCapabilities? capabilities = null)
    {
        Transport = transport;
        GetState = getState;
        SetState = setState;
        ModelId = modelId;
        OnCustom = onCustom;
        Capabilities = capabilities ?? new TransportCapabilities(
            SupportsReceive: GetSupportsReceive(transport));
        Phase = Phase.Unopened;
        _listening = false;
    }

    private static bool GetSupportsReceive(object transport)
    {
        var prop = transport.GetType().GetProperty("SupportsReceive");
        if (prop != null && prop.CanRead)
            return (bool)prop.GetValue(transport)!;
        return false;
    }

    public void Open()
    {
        if (Phase == Phase.Open) return;
        Execute(Lifecycle.Reduce(Phase, new Open(), GetState(), Capabilities));
    }

    public void SendState(HashSet<string>? include = null)
    {
        Execute(Lifecycle.Reduce(Phase, new SendState(include), GetState(), Capabilities));
    }

    public void SendCustom(object? content, List<object?>? buffers = null)
    {
        Execute(Lifecycle.Reduce(Phase, new SendCustom(content, buffers), GetState(), Capabilities));
    }

    public void Close()
    {
        Execute(Lifecycle.Reduce(Phase, new Close(), new Dictionary<string, object?>(), Capabilities));
    }

    public Dictionary<string, object?> Mimebundle(string reprText = "")
    {
        return Core.Mimebundle(ModelId, reprText);
    }

    private void Execute((Phase NewPhase, List<object?> Effects) result)
    {
        Phase = result.NewPhase;
        foreach (var effect in result.Effects)
            ExecOne(effect);
    }

    private void ExecOne(object? effect)
    {
        switch (effect)
        {
            case Send s:
                Core.TransportSend(Transport, s.MsgType, s.Data, s.Buffers, s.Metadata);
                if (s.MsgType == "comm_open")
                {
                    var cid = Core.CommId(Transport);
                    if (!string.IsNullOrEmpty(cid))
                    {
                        ModelId = cid;
                        Execute(Lifecycle.Reduce(Phase, new CommIdAssigned(cid), new Dictionary<string, object?>(), Capabilities));
                    }
                }
                break;
            case Listen:
                if (!_listening)
                {
                    Core.TransportOnMessage(Transport, (data, bufs) => HandleInbound(data, bufs));
                    _listening = true;
                }
                break;
            case ApplyState a:
                SetState?.Invoke(a.State);
                break;
            case InvokeCustom ic:
                OnCustom?.Invoke(ic.Content, ic.Buffers);
                break;
            case Error err:
                throw new InvalidOperationException(err.Message);
        }
    }

    private void HandleInbound(Dictionary<string, object?> data, List<object?>? buffers)
    {
        Execute(Lifecycle.Reduce(Phase, new Inbound(data, buffers), GetState(), Capabilities));
    }
}

// ---- protocol core ----
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

    public static Dictionary<string, object?> ImmutableFields() =>
        ImmutableFields(AnywidgetModuleVersion);

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

    private const int MaxDepth = 500;

    private static object? Separate(
        object? sub, List<object?> path, List<List<object?>> paths, List<byte[]> buffers,
        HashSet<object>? ancestors = null, int depth = 0)
    {
        if (!IsContainer(sub))
            return sub;
        if (depth > MaxDepth)
            throw new InvalidOperationException(
                $"state nesting exceeds {MaxDepth} levels at path [{string.Join(", ", path)}]");
        ancestors ??= new HashSet<object>(ReferenceEqualityComparer.Instance);
        if (!ancestors.Add(sub!))
            throw new InvalidOperationException(
                $"cyclic reference detected in state at path [{string.Join(", ", path)}]");
        try
        {
            switch (sub)
            {
                case Dictionary<string, object?> obj:
                    var outObj = new Dictionary<string, object?>();
                    foreach (var (k, v) in obj)
                    {
                        var seg = new List<object?>(path) { k };
                        if (IsBinary(v)) { paths.Add(seg); buffers.Add((byte[])v!); }
                        else if (IsContainer(v)) outObj[k] = Separate(v, seg, paths, buffers, ancestors, depth + 1);
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
                        else if (IsContainer(v)) outArr.Add(Separate(v, seg, paths, buffers, ancestors, depth + 1));
                        else outArr.Add(v);
                    }
                    return outArr;

                default:
                    return sub;
            }
        }
        finally
        {
            ancestors.Remove(sub!);
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
    public sealed record Update(object? State, List<List<object?>> BufferPaths) : InboundMessage;
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
                (data.GetValueOrDefault("buffer_paths") as List<object?>
                    ?? new List<object?>()).Cast<List<object?>>().ToList()),
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

    // ---- transport seam ----

    /// <summary>Whether the transport can receive frontend→kernel messages.</summary>
    public static bool SupportsReceive(object transport) => false;

    /// <summary>The transport's comm id; empty until opened.</summary>
    public static string CommId(object transport) => "";

    /// <summary>Build the widget-view mimebundle used for display.</summary>
    public static Dictionary<string, object?> Mimebundle(string modelId, string reprText = "")
    {
        var bundle = new Dictionary<string, object?>
        {
            ["application/vnd.jupyter.widget-view+json"] = new Dictionary<string, object?>
            {
                ["version_major"] = (long)ProtocolVersionMajor,
                ["version_minor"] = (long)ProtocolVersionMinor,
                ["model_id"] = modelId,
            },
        };
        if (!string.IsNullOrEmpty(reprText))
            bundle["text/plain"] = reprText;
        return bundle;
    }

    /// <summary>Send a Jupyter comm message to the frontend.</summary>
    public static void TransportSend(object transport, string msgType, Dictionary<string, object?> data,
        List<object?>? buffers = null, Dictionary<string, object?>? metadata = null)
    {
        throw new NotSupportedException(
            "TransportSend is not implemented. Override this method or use a concrete transport.");
    }

    /// <summary>Register an inbound message callback.</summary>
    public static void TransportOnMessage(object transport,
        Action<Dictionary<string, object?>, List<object?>?> callback)
    {
        throw new NotSupportedException(
            "TransportOnMessage is not implemented. Override this method or use a concrete transport.");
    }
}
