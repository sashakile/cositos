# Porting a `cositos` backend to a new Jupyter kernel language

This guide is for someone who knows a language ecosystem (Julia, C#, R, …) and wants a
`cositos`/anywidget-style backend there. You do **not** write any JavaScript — you reuse
anywidget's published `AnyModel`/`AnyView` frontend.

## What you implement

Exactly two things:

1. **A `Transport` adapter** over your kernel's comm API.
2. **The pure core** — message builders + buffer split/merge — in your language. This is
   ~150 lines and is fully specified by the golden fixtures.

Everything else (observer autodetection, ESM hot-reload, host-idiomatic state objects)
is optional ergonomics you can add later.

## Step 1 — Implement the Transport

Your kernel exposes some comm surface. Map it to:

| Core needs | Python (`comm`) | Deno | IJulia | dotnet-interactive |
|---|---|---|---|---|
| open + send | `comm.create_comm` / `comm.send` | `Deno.jupyter.broadcast("comm_open"/"comm_msg", …)` | `Comm(...)` / `send` | `Kernel.SendAsync` |
| receive | `comm.on_msg` | (limited) | `comm.on_msg` | comm handler |
| `supports_receive` | `True` | often `False` | `True` | `True` |

If your kernel is broadcast-only (can't route frontend→kernel replies), set
`supports_receive = False`; the core degrades to one-way widgets.

## Step 2 — Reproduce the protocol

Implement, matching `fixtures/*.json` byte-for-byte (modulo comm_id and buffer encoding):

- `build_comm_open(state) -> (data, buffers, metadata)` — merge the seven immutable
  fields (`_model_module="anywidget"`, `AnyModel`/`AnyView`, `_view_count=null`,
  version), strip buffers, `metadata = {"version": "2.1.0"}`.
- `build_update(state) -> (data, buffers)` — `{method:"update", state, buffer_paths}`.
- `build_custom(content)` — `{method:"custom", content}`.
- `parse_message(data)` — dispatch on `method`: `update` | `request_state` | `custom`.
- `remove_buffers` / `put_buffers` — protocol v2 nested-buffer rules: a binary value at
  a dict key is *removed* and its key path recorded; at a list index it becomes `null`.

## Step 3 — Certify

Load `fixtures/*.json` in your test runner and assert your builders reproduce them.
`fixtures/update_nested_buffer.json` is the important one — it exercises the nested
buffer split that ports most often get wrong.

Buffers in fixtures are base64-encoded under `buffers_b64` so the contract is
language-neutral; decode to raw bytes when comparing.

## Reference

- Wire protocol: <https://github.com/jupyter-widgets/ipywidgets/blob/main/packages/schema/messages.md>
- Python reference: `src/cositos/` in this repo.
- Design rationale: `.wai/projects/cositos-core/design/`.
