# Research: Porting the anywidget backend to a new Jupyter kernel language

## Question (from chat.md)
How much work is it to port anywidget's *backend* to another language with a Jupyter
kernel (Python, Julia, C#, R, ...)? What are the main challenges/blockers?

## Answer in one line
The backend is small. The hard part is (a) speaking the ipywidgets **comm** wire
protocol exactly and (b) reproducing anywidget's tiny **conventions** on top of it. No
new frontend is needed — anywidget's existing `AnyModel`/`AnyView` JS is reused verbatim.

## What the backend actually has to do
Reverse-engineered from three reference implementations in this repo:

1. `packages/deno/src/mod.ts` — the Deno backend (~350 LOC). Wraps
   `Deno.jupyter.broadcast(msg_type, content, {buffers, metadata})`.
2. `anywidget/_descriptor.py` — the experimental Python "thin layer over `comm`".
3. `ipywidgets/packages/schema/messages.md` — the authoritative wire protocol.

### Core responsibilities (the whole surface)
1. **Open a comm** on target `jupyter.widget` with `comm_open`, carrying initial state
   plus the six required immutable fields:
   `_model_module="anywidget"`, `_model_name="AnyModel"`, `_model_module_version`,
   `_view_module="anywidget"`, `_view_name="AnyView"`, `_view_module_version`,
   `_view_count=null`, and the anywidget-specific `_esm` (+ optional `_css`,
   `_anywidget_id`).
   Metadata must include the protocol version: `{"version": "2.1.0"}`.
2. **Send state kernel→frontend**: `comm_msg` with
   `{"method":"update","state":{...},"buffer_paths":[...]}`.
3. **Receive state frontend→kernel**: handle `comm_msg` with `method` in
   `{update, request_state, custom}`. On `request_state`, resend full state.
4. **Buffer handling**: strip binary values (bytes/bytearray/memoryview) out of the
   JSON state into a parallel `buffers` list + `buffer_paths` (v2 protocol: buffers may
   be nested anywhere; list slots become `null`, dict keys are removed). Inverse
   (`put_buffers`) when receiving.
5. **Display**: emit a mimebundle with
   `application/vnd.jupyter.widget-view+json` → `{version_major, version_minor, model_id}`.

That is the entire contract. Everything else (traitlets, psygnal, pydantic, dataclass
autodetection in `_descriptor.py`) is *ergonomics for a specific host language*, not
part of the protocol.

## The wire protocol (messages.md v2 / 2.1.0), condensed
- Target: `jupyter.widget` (per-widget comm). Optional `jupyter.widget.control` for
  bulk state fetch (`request_states` → `update_states`).
- `comm_open.data = {state, buffer_paths}`; metadata `{version:"2.0.0"+}`.
- `update` (both directions): `{method, state, buffer_paths}`. v2 unified the field
  names in both directions (v1 used `backbone`/`sync_data`/`buffer_keys` frontend→kernel).
- `echo_update` (opt-in, ≥2.1.0): kernel rebroadcasts a frontend update to all
  frontends. Not required for a first port.
- `request_state` → kernel replies with full `update`.
- `custom`: `{method:"custom", content, buffers}`.
- v2 buffer_paths: nested paths; `[['x'], ['y','z',0]]`.

## Where the bindings live now (answering the chat's "point me at it")
- **Python (ipywidgets-based, production)**: buried in ipywidgets `Widget` internals;
  anywidget's `widget.py` subclasses `ipywidgets.DOMWidget`.
- **Python (experimental, thin)**: `anywidget/_descriptor.py` + `_util.py`. This is the
  cleanest reference — it talks directly to the `comm` package, no ipywidgets.
- **Deno**: `packages/deno/src/mod.ts` wraps `Deno.jupyter.broadcast`.

## Main challenges / blockers (the real answer to the chat)
1. **No stable comm abstraction across kernels.** Each kernel exposes comms
   differently: Python has the `comm` package + `ipykernel`; Deno has
   `Deno.jupyter.broadcast` (broadcast-only, no per-comm reply routing today);
   Julia's `IJulia` and C#'s `dotnet-interactive` each have their own comm surfaces;
   Xeus kernels differ again. The port's hardest job is a **per-kernel comm adapter**.
2. **Broadcast vs. targeted send + msg routing.** Kernel→frontend is broadcast to all
   frontends; frontend→kernel replies must be routed back to the right widget by
   `comm_id`. Kernels that only expose broadcast (early Deno) can't easily receive.
3. **Binary buffer serialization.** Every kernel represents bytes differently; the
   `remove_buffers`/`put_buffers` nesting logic must be reimplemented faithfully or
   binary traits (numpy arrays, images) break.
4. **State model / observability.** Detecting "a field changed" to auto-send updates is
   language-specific (traitlets/psygnal in Python, `@observable` elsewhere). anywidget
   core wisely refuses to own this — bindings must.
5. **Version negotiation.** Protocol v1 used a `jupyter.widget.version` handshake; v2
   dropped it and relies on the maintainer pinning compatible versions. A port must
   pin `_model_module_version` to a frontend anywidget release it was tested against.
6. **ESM transport & lifecycle.** `_esm`/`_css` are just state strings; the front end
   fetches/executes them. A port must decide how the host language authors/loads ESM
   (inline string, file with hot-reload à la `FileContents`, bundler output).

## Design implication for `cositos`
The maintainer's stated goal (from chat.md): keep anywidget core free of per-language
bindings; let ecosystem experts own each host binding. `cositos` should therefore be a
**thin, protocol-faithful core** with a **pluggable comm-transport seam** — mirroring the
Deno `Comm` class and the Python `open_comm`/`send_state`/`_handle_msg` trio, but with
the transport abstracted so each kernel supplies its own send/receive.

## Sources (grounding)
- `anywidget/packages/deno/src/mod.ts:70-152` (Comm.init / sendState / mimebundle)
- `anywidget/anywidget/_descriptor.py:110-160` (open_comm), `:300-360` (send_state/_handle_msg)
- `anywidget/anywidget/_util.py:12-31` (protocol constants, DEFAULT_ESM), `:40-150` (buffers)
- `ipywidgets/packages/schema/messages.md` (protocol v1 & v2, control v1)

