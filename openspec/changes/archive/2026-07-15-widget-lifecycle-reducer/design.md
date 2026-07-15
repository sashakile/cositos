## Context

cositos's current `Widget` class (Python `src/cositos/model.py`, Julia `Cositos.jl` lines ~383-475) is the only part of the core that breaks the project's "pure, fixture-testable" design rule. It is a mutable, imperative object: it manages an `_opened`/`opened` flag, decides *and acts* in the same method, and its behavior is specified only through inline comments and another language's source code. The protocol core (`protocol.py`, `buffers.py`, `serialize.py`) is already composed of pure functions fixture-tested against `fixtures/*.json`; the lifecycle should follow the same shape.

The evaluation (`docs/evaluations/cositos-abstraction-proposal.md`) identified five hidden lifecycle rules across languages: idempotent `open`, identity re-merge on full `send_state`, comm-id adoption after open, one-way degrade via `supports_receive`, and per-transport capability gaps (Clojure cannot express buffers/custom/request_state). The Julia identity-remerge bug (fixed in `55ce62c`) validated the thesis — a fixture-tested reducer would have caught it.

## Goals / Non-Goals

**Goals:**
- Define a pure `reduce(phase, event, state) → (new_phase, effects[])` function encoding the widget lifecycle state machine.
- Define a fixture-serializable effect vocabulary (`Send`, `Listen`, `ApplyState`, `InvokeCustom`) as plain data — never side-effecting.
- Install the reducer in Python first (parity-tested against the existing `Widget` class), then Julia, then certify C#/R shells.
- Update `docs/porting.md` to include a Step 5 (lifecycle) referencing the reducer.
- Add spec-level requirements for buffer-split cycle detection and depth capping across all ports.
- Generalize `supports_receive` into per-event-kind capability flags (`supports_request_state`, `supports_custom`, `supports_buffers`).

**Non-Goals:**
- No compiled core, FFI layer, WASM, or RPC service (rejected per §4 Option A/B — the buffer-split algorithm is too small to justify marshaling overhead).
- No change to Clojure's `clojupyter_transport.clj` capability set — its gaps (no buffers, no custom, no request_state) are a genuine transport limitation, not a bug to fix. The capability flags exist so the shell never produces events the transport cannot carry.
- No new language port. The reducer is designed for a future 6th language port but this change does not add one.
- No observer autodetection or host-idiomatic state ergonomics — those remain per-language optional extras.

## Decisions

### D1: Pure reducer as a function, not a class or macro

**Decision:** `reduce(phase, event, state) → (new_phase, effects[])` is a plain function, data-in/data-out, exactly like `build_comm_open` and `remove_buffers`.

**Rationale:** The protocol core already uses this shape successfully across five languages. A function is trivially fixture-testable: serialize the `(phase, event, state)` triple as JSON input, assert the `(new_phase, effects)` pair as JSON output. No object state, no mocking, no kernel. Every language in cositos's portfolio (Python, Julia, Clojure, C#, R) can call a pure function; none requires a class or macro for this pattern.

### D2: Phase as a simple enum (Unopened / Open / Closed)

**Decision:** Three discrete phases, represented as strings (`"unopened"`, `"open"`, `"closed"`) in languages without real tagged unions (R, C#), or as proper ADTs/enums where available (Julia, Python, Clojure).

**Rationale:** The current code already has exactly three phases: before-open (could also be called "initial"), open, and closed. No fourth phase (e.g., "error") has been needed across five ports. Using strings for the data-on-wire representation keeps the fixture format cross-language without a schema compiler.

### D3: Effect vocabulary as a tagged list

**Decision:** Effects are plain lists of `{"kind": "send", "msg_type": ..., "data": ..., "buffers": ..., "metadata": ...}` maps (or equivalent per-language data — keyword-keyed maps in Clojure, named tuples in Julia, dataclass instances in Python).

**Effect kinds:**
| kind | fields | semantics |
|---|---|---|
| `send` | `msg_type` ∈ `{"comm_open", "comm_msg", "comm_close"}`, `data`, `buffers`, `metadata` | Call `transport.send(msg_type, data, buffers=buffers, metadata=metadata)` |
| `listen` | — | Call `transport.on_message(callback)` (shell wires the callback back to the event loop) |
| `apply_state` | `state` | Call host's `set_state(state)` |
| `invoke_custom` | `content`, `buffers` | Call host's `on_custom(content, buffers)` |
| `error` | `message: str` | Convert to a language-appropriate exception or log. The shell SHALL raise `RuntimeError(message)` (or equivalent) in response to an error effect — never silently swallow it. |

**Rationale:** A fixed, small set of effect kinds keeps the shell trivial (a `match`/`case`/`switch` with 4 branches). The shell never needs to inspect effect *content* beyond dispatching by kind — all logic is in the reducer.

### D4: Event vocabulary

**Decision:** Events that `reduce` accepts:

| event | payload | source |
|---|---|---|
| `open` | — | User/host calls `shell.open()` |
| `send_state` | `include: Optional[set[str]]` | User/host calls `shell.send_state(...)` |
| `send_custom` | `content, buffers` | User/host calls `shell.send_custom(...)` |
| `inbound` | `message` (parsed via `parse_message`) | Transport's `on_message` callback |
| `close` | — | User/host calls `shell.close()` |
| `comm_id_assigned` | `id: str` | Shell reads `transport.comm_id()` after a `send("comm_open", ...)` effect |

**Rationale:** Mapped directly from the existing `Widget` methods. The `comm_id_assigned` event is the feedback loop from the imperative shell — synchronous, not async (confirmed in §7.3 of the evaluation).

### D5: Capability flags generalize `supports_receive`

**Decision:** Replace the single `supports_receive: bool` with an explicit set or struct:

```python
@dataclass(frozen=True)
class TransportCapabilities:
    supports_receive: bool = True
    supports_request_state: bool = True
    supports_custom: bool = True
    supports_buffers: bool = True
```

The shell queries these once at construction and passes them into `reduce` as part of the initial state (or as a separate parameter — TBD in implementation). `reduce` never produces a `send` effect with buffers if `supports_buffers` is false, etc.

**Rationale:** Clojure's transport cannot express buffers, custom messages, or request_state — that is a permanent, documented limitation of the `comm-atom` primitive, not a bug. Silently dropping effects in the shell (rather than the reducer refusing to produce them) would let bugs through. Making capability flags explicit in the reducer means a transport that declares `supports_custom=False` will never even try to emit a custom send — the debate about it happens once, in the transport definition, not at runtime.

### D6: Lifecycle fixtures live in `fixtures/lifecycle/`

**Decision:** Golden files for `reduce` input/output, one JSON array per event type:

```json
// fixtures/lifecycle/open.json
[
  ["unopened", {"kind": "open"}, {"_esm": "...", "value": 0}, "open", [{"kind": "send", "msg_type": "comm_open", "data": {...}, "buffers": [], "metadata": {"version": "2.1.0"}}, {"kind": "listen"}]]
]
```

Each fixture file is a JSON array of tuples: `[phase_in, event, state_in, phase_out, effects_out]`. The `state_in` is the current host state dict; `state_out` is omitted from the fixture format because the reducer's output for `state_out` is always a copy of `state_in` (the reducer does not mutate host state — mutations flow through `apply_state` effects).

**Rationale:** The protocol fixtures live in `fixtures/*.json`; the lifecycle fixtures follow the same convention but in a separate `fixtures/lifecycle/` directory so a port can certify either or both (C# and R today only certify the protocol fixtures). The format is a simple array of `[phase_in, event, state_in, phase_out, effects_out]` tuples, trivially parsable in every language.

### D7: Imperative shell structure

**Decision:** The shell for each language follows this skeleton. The shell owns the event loop: it holds the current phase, the host state (fetched via `get_state()`), and the capability flags, feeds them into `reduce`, and walks the returned effects.

```
shell = WidgetShell(transport, get_state, set_state, on_custom, capabilities)

# open() is called by user code:
def shell.open():
    current_state = self.get_state()
    (phase, effects) = reduce(self.phase, Open(), current_state, self.capabilities)
    self.phase = phase
    for effect in effects:
        execute(effect)
    # ...
```

The `execute` helper dispatches effects:

```
def execute(effect):
  match effect.kind:
    "send"         => transport.send(effect.msg_type, effect.data, effect.buffers, effect.metadata)
    "listen"       => transport.on_message(callback that feeds inbound back as Inbound event)
    "apply_state"  => host.set_state(effect.state)
    "invoke_custom" => host.on_custom(effect.content, effect.buffers)
    "error"        => raise RuntimeError(effect.message)
  # after executing a send with msg_type="comm_open":
  if effect.kind == "send" and effect.msg_type == "comm_open":
    id = transport.comm_id()
    if id:
      (phase, effects) = reduce(self.phase, CommIdAssigned(id), self.state, self.capabilities)
      self.phase = phase
      for effect in effects:
        execute(effect)  # typically 0 effects for a comm_id_assigned event
```

The comm-id adoption loop can be a simple 1-extra-step sequence — no unbounded looping expected (confirmed in §7.3 of the evaluation).

**Rationale:** The shell is intentionally minimal. All branching logic lives in the reducer, which is fixture-tested. The shell is the one place each language couples to its own `Transport` and host-callback conventions, and it is too trivial to get wrong.

## Risks / Trade-offs

### R1: One more concept vs. today's plain object
The reducer + shell split is one more concept than today's flat `Widget` class. A porter who only wants to send a single message can ignore the reducer and call `transport.send(...)` directly — the reducer is for ports that want a full live widget with bidirectional state sync. Mitigation: `docs/porting.md` explicitly separates "minimal fixture certification" (steps 1-4, unchanged) from "live widget" (new step 5).

### R2: Clojure's capability gaps are permanent, not software-fixable
The per-event-kind flags document rather than fix Clojure's limitations. A Clojure porter who wants buffers or custom messages must use Clay (`docs/hosts.md`) instead of the `clojupyter_transport`. Mitigation: the flag approach makes this choice explicit and checkable at porting time rather than a discovery during runtime debugging.

### R3: Fixture suite growth
Adding `fixtures/lifecycle/*.json` doubles the fixture surface. Mitigation: the lifecycle fixtures are drastically simpler than protocol fixtures (fixed small input → fixed small output, no raw binary encoding). Optionally, lifecycle fixtures can be property-tested rather than golden-file-tested in a second pass.

### R4: Existing Widget class becomes a deprecated shell
For one release cycle, the reducer and the old `Widget` class coexist — Python tests certify both produce identical behavior. Once the reducer is fixture-certified in Python and Julia, the old `Widget` internals are replaced by the shell (the public API does not change). No breaking changes to end-user code at any point.

## Open Questions

1. **Capability flags: part of state or separate parameter?** Passing them as part of the initial `state` dict is simpler (one function signature) but conflates transport capabilities with widget state. A separate parameter is cleaner but language-dependent. Decide during Python implementation.
2. **Error handling convention:** What does the reducer do on invalid transitions (e.g., `send_state` from `Unopened`)? Raise? Return an error effect? The existing `Widget` raises a `RuntimeError` — the reducer should produce an error effect that the shell converts to a raise.
3. **Effect deduplication for `listen`:** The reducer always emits `listen` on `open` from `"unopened"` (if capabilities allow receive). The shell is responsible for idempotency — it calls `transport.on_message()` at most once. If `listen` appears in two effect lists, the second call to `on_message` is a no-op (the shell checks a flag, matching current `pending`-callback behavior in `CommTransport`).
