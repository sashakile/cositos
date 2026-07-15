---
title: "Porting a cositos backend to a new Jupyter kernel language"
---


> **What this page is:** How to implement a cositos backend in a new language — Transport
> adapter, pure core, lifecycle shell, and certification against fixtures.

This guide is for someone who knows a language ecosystem (Julia, C#, R, …) and wants a
`cositos`/anywidget-style backend there. You do **not** write any JavaScript — you reuse
anywidget's published `AnyModel`/`AnyView` frontend.

Before you start, read the [architecture](explanation/architecture.qmd) page to
understand the **lifecycle reducer** — the pure state machine that every backend
implements. The [lifecycle spec](reference/specs.qmd#lifecycle) and
[lifecycle-shell spec](reference/specs.qmd#lifecycle-shell) are the full normative
contracts.

## What you implement

Three things, covered across five steps below (Steps 1–2 and 5 are implementation;
Steps 3–4 verify what you built):

1. **A `Transport` adapter** over your kernel's comm API.
2. **The pure core** — message builders + buffer split/merge — in your language. This is
   ~150 lines and is fully specified by the golden fixtures.
3. **The lifecycle shell** — the thin imperative bridge that calls the lifecycle reducer
   and executes the returned effects. This is ~50 lines and is specified by the
   [lifecycle-shell spec](reference/specs.qmd#lifecycle-shell).

Everything else (observer autodetection, ESM hot-reload, host-idiomatic state objects)
is optional ergonomics you can add later.

## Step 1 — Implement the Transport

Your kernel exposes some comm surface. Map it to:

| Core needs | Python (`comm`) | Deno | IJulia | dotnet-interactive | clojupyter (crack, see caveat) |
|---|---|---|---|---|---|
| open + send | `comm.create_comm` / `comm.send` | `Deno.jupyter.broadcast("comm_open"/"comm_msg", …)` | `Comm(...)` / `send` | `Kernel.SendAsync` | `comm-atom/create-and-insert` + `state-update!` |
| receive | `comm.on_msg` | (limited) | `comm.on_msg` | comm handler | `comm-atom/watch` |
| `supports_receive` | `True` | often `False` | `True` | `True` | `True` (state-sync only — no buffers, no `custom`) |

If your kernel is broadcast-only (can't route frontend→kernel replies), set
`supports_receive = False`; the core degrades to one-way widgets.

**clojupyter caveat.** Unlike the other four, clojupyter ships no *public* comm-open API
at all — the columns above describe `cositos.clojupyter-transport`
(`clojure/dev/cositos/clojupyter_transport.clj`), which reaches
`clojupyter.state/current-context`, an internal, version-coupled implementation detail
(confirmed live in `cositos-059.9`). It supports the `update` round trip only: no binary
buffers, no `custom` messages (every sender on clojupyter's `comm-atom`, public or
private, hard-wraps its argument as an `update`). If you don't need those, and accept
the internal-API risk, it works; otherwise use **Clay** (`docs/hosts.md`) instead — a
genuinely public API with full buffer/custom-message support, at the cost of not being
a Jupyter kernel.

## Step 2 — Reproduce the protocol

Implement, matching `fixtures/*.json` byte-for-byte (modulo comm_id and buffer encoding):

- `build_comm_open(state) -> (data, buffers, metadata)` — merge the seven immutable
  fields (`_model_module="anywidget"`, `AnyModel`/`AnyView`, `_view_count=null`,
  version), strip buffers, `metadata = {"version": "2.1.0"}`.
- `build_update(state) -> (data, buffers)` — `{method:"update", state, buffer_paths}`.
- `build_custom(content)` — `{method:"custom", content}`.
- `parse_message(data)` — dispatch on `method`: `update` | `request_state` | `custom`;
  an unknown or missing `method` is *ignored* (return a benign sentinel, never raise) so a
  newer frontend's messages stay forward-compatible.
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
- `load_document(document) -> entries` — the exact inverse. Validate the envelope at the
  boundary: reject a missing/non-mapping `state` and an unsupported `version_major` with a
  clear error (a higher `version_minor` is accepted). References between widgets are
  plain `"IPY_MODEL_<id>"` strings, so loading is a flat id-keyed pass (reference cycles
  are safe).
- Reject empty or duplicate `model_id`s when building a document (it is the primary key).
- **Compare buffers by raw bytes**, not by your language's typed-array equality: a
  `float32` view and a plain-bytes view with identical bytes may compare unequal. The
  fixture's `plot` model carries a `float32` array buffer plus `shape`/`dtype` state to
  exercise this.

The round-trip `load_document(dump_document(x)) == x` is the law to test (the Python
reference also property-tests it).

## Step 5 — Implement the lifecycle shell

The pure message builders from Step 2 cover message *shaping*, but a live widget also
needs a **lifecycle** — opening the comm, sending state, receiving updates, closing.
cositos encodes this as a pure reducer:

```
reduce(phase, event, current_state, capabilities)
    → (new_phase, effects[])
```

Every backend implements the same reducer. The **imperative shell** (`WidgetShell` in
Python; see `src/cositos/lifecycle.py`) is the thin per-language bridge that:

1. Calls `reduce` with the current phase, the user's event, the widget state, and the
   transport's capability flags.
2. Walks the returned effect list and executes each one:
   - `Send(msg_type, data, buffers, metadata)` → `transport.send(...)`
   - `Listen()` → `transport.on_message(callback)`
   - `ApplyState(state)` → host's `set_state`
   - `InvokeCustom(content, buffers)` → host's custom handler
   - `Error(message)` → raise an error
3. After a `comm_open` send, reads the transport's assigned comm id and feeds it back
   as a `CommIdAssigned` event. This is needed because the transport may assign a
   different comm id than the one the shell passed — the feedback loop ensures the shell
   uses the real id for subsequent mimebundle calls.

See the [lifecycle-shell spec](reference/specs.qmd#lifecycle-shell) for the full
contract and the [API reference](reference/index.qmd#lifecycle) for the event and
effect type signatures.

## Reference

- Wire protocol: <https://github.com/jupyter-widgets/ipywidgets/blob/main/packages/schema/messages.md>
- Python reference: `src/cositos/` in this repo.
- [Architecture & reducer design](explanation/architecture.qmd) — how the lifecycle
  reducer, Transport seam, and Document model fit together.
- [Lifecycle spec](reference/specs.qmd#lifecycle) — the normative reducer contract.
- [Lifecycle-shell spec](reference/specs.qmd#lifecycle-shell) — the imperative shell
  contract.
- [API reference](reference/index.qmd) — full API including lifecycle events, effects,
  and capabilities.
- Cross-language symbol lookup: `docs/reference/api-cheatsheet.qmd`.
