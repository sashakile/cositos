# Design: `cositos` — a portable anywidget backend core

## Goal
A library, inspired by anywidget, that lets you define a widget's front-end once and
drive it from *any* Jupyter kernel language (Python, Julia, C#, R, …) without the core
taking on per-language binding responsibility. Directly addresses the chat.md request.

## Design tenets (derived from research + the maintainer's stated constraint)
1. **The core owns the protocol, not the bindings.** The chat's key blocker: "avoid
   anywidget core taking on responsibility for such bindings." So cositos's core is pure
   protocol logic (message shaping, buffer split/merge, state diffing) with **no kernel
   or transport code**.
2. **Transport is a seam.** Every kernel exposes comms differently (Python `comm`,
   `Deno.jupyter.broadcast`, IJulia, dotnet-interactive). The core depends on a small
   `Transport` interface (send + on-receive); each host supplies an adapter.
3. **Reuse the frontend verbatim.** No new JS. Emit `_model_module="anywidget"`,
   `AnyModel`/`AnyView`, so the published anywidget front end renders `cositos` widgets.
4. **The contract is data, not code.** The cross-language guarantee is a set of
   **golden message fixtures** (JSON) that any port must reproduce byte-for-byte
   (modulo comm_id/ordering). This is how new-language ports self-certify.

## Architecture

```
                    ┌─────────────────────────────────────────┐
   host language    │  cositos-core (pure, no I/O)             │
   state object ───▶│  • open()    -> comm_open payload        │
   (traits/struct)  │  • update()  -> comm_msg payload         │
                    │  • recv(msg) -> parsed inbound event     │
                    │  • buffers: split() / merge()            │
                    │  • mimebundle()                          │
                    └───────────────┬─────────────────────────┘
                                    │ Transport interface
                                    │  send(msg_type, content, buffers, metadata)
                                    │  on_message(callback)
                    ┌───────────────┴─────────────────────────┐
                    │  host adapter (per kernel, thin)         │
                    │  Python: comm.create_comm / on_msg       │
                    │  Deno:   Deno.jupyter.broadcast          │
                    │  Julia:  IJulia comm API                 │
                    │  C#:     dotnet-interactive comm         │
                    └──────────────────────────────────────────┘
```

### Core modules (language-neutral names)
- `protocol` — constants (`PROTOCOL_VERSION="2.1.0"`, module/name fields, default ESM),
  message builders (`build_comm_open`, `build_update`, `build_custom`), and the inbound
  parser (`parse_message` → `Update{state,buffer_paths}` | `RequestState` | `Custom`).
- `buffers` — `remove_buffers(state) -> (state, buffer_paths, buffers)` and
  `put_buffers(state, paths, buffers)`; faithful port of the v2 nested-buffer rules.
- `model` — a `Widget` façade tying a state getter/setter to a `Transport`: `open()`,
  `send_state(include)`, `_handle(msg)`, `close()`. Mirrors Python `ReprMimeBundle` and
  Deno `Comm`, minus the observer autodetection.
- `transport` — the `Transport` interface only. No implementations in core.

### Reference implementation language: Python
Chosen for the *reference* because: `comm` + `uv` are available for real tests now, and
a clean-room thin core (no ipywidgets) mirrors `_descriptor.py` while proving the seam.
The reference is deliberately NOT the deliverable's ceiling — it exists to generate and
validate the golden fixtures. Other ports (Julia/C#/R) are downstream and out of scope
for v0.

### Cross-language contract: golden fixtures
`fixtures/*.json` capture the exact `comm_open` / `update` / `custom` payloads and the
buffer split for representative states (scalars, nested, binary buffers, widget refs).
A port passes if `build_*`/`remove_buffers` reproduce these. This is the mechanism that
lets ecosystem experts own bindings without the core knowing about their language.

## Key decisions & trade-offs
| Decision | Alternative rejected | Why |
|---|---|---|
| Pure core + transport seam | Bake comm into core | Matches maintainer constraint; testable without a kernel |
| Reuse anywidget frontend | Ship own JS | Zero frontend maintenance; instant compatibility |
| Golden JSON fixtures as contract | Shared Rust core via FFI | FFI into each kernel runtime is heavy/awkward; the backend is ~350 LOC of glue best written natively per host |
| Python reference first | Deno/TS first | Toolchain (`uv`) present; direct comparison to `_descriptor.py` |
| Pin protocol 2.1.0 | Support v1 handshake | v2 dropped the `jupyter.widget.version` handshake; new ports need only v2 |

## Explicit non-goals (v0)
- Observer autodetection (traitlets/psygnal/pydantic) — host ergonomics, added per host.
- `echo_update` multi-frontend echo — optional in the protocol; defer.
- `jupyter.widget.control` bulk-state comm — optional; defer.
- Actual Julia/C#/R adapters — downstream; v0 ships the core + Python ref + fixtures.

## Risks
- **Comm reply routing on broadcast-only kernels** (early Deno): frontend→kernel may not
  route back per comm. Mitigation: `Transport` declares `supports_receive`; degrade to
  one-way widgets when false.
- **Buffer-rule drift**: the nested v2 buffer logic is subtle. Mitigation: golden
  fixtures include nested-buffer cases; property test round-trip `merge(split(x)) == x`.

