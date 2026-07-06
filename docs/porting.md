---
title: "Porting a cositos backend to a new Jupyter kernel language"
---


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

## Step 4 — Certify serialization (save/restore)

A backend may also serialize widget state to the ipywidgets **Widget State JSON schema
v2** (`application/vnd.jupyter.widget-state+json`) so a UI can be saved and reconstructed.
Certify against `fixtures/widget-state.json`:

- `dump_document(entries) -> document` — map each `(model_id, state)` to a record
  `{model_name, model_module, model_module_version?, state, buffers?}` and wrap it in
  `{version_major: 2, version_minor: 0, state: {model_id: record}}`. **Note the two
  version numbers:** the state-format version is `2.0`, distinct from the protocol version
  `2.1.0`. Binary buffers become `{path, encoding:"base64", data}` records; omit the
  `buffers` key when a model has none.
- `load_document(document) -> entries` — the exact inverse. References between widgets are
  plain `"IPY_MODEL_<id>"` strings, so loading is a flat id-keyed pass (reference cycles
  are safe).
- Reject empty or duplicate `model_id`s when building a document (it is the primary key).
- **Compare buffers by raw bytes**, not by your language's typed-array equality: a
  `float32` view and a plain-bytes view with identical bytes may compare unequal. The
  fixture's `plot` model carries a `float32` array buffer plus `shape`/`dtype` state to
  exercise this.

The round-trip `load_document(dump_document(x)) == x` is the law to test (the Python
reference also property-tests it).

## Reference

- Wire protocol: <https://github.com/jupyter-widgets/ipywidgets/blob/main/packages/schema/messages.md>
- Python reference: `src/cositos/` in this repo.
- Design rationale: `.wai/projects/cositos-core/design/`.
