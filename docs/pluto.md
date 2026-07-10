---
title: "Using cositos widgets in Pluto.jl"
---


Pluto is **not** Jupyter — there is no comm protocol. Pluto is reactive-cell-based:
widgets render via `Base.show(::MIME"text/html")`, two-way binding happens through
`@bind` + `AbstractPlutoDingetjes.Bonds`, and Julia→JS data travels embedded in the
rendered HTML. cositos reuses the **same anywidget ESM** across both worlds by supplying
a Pluto-specific transport.

## How it maps

| anywidget concept | Jupyter | Pluto (cositos) |
|---|---|---|
| Frontend model | `AnyModel` over the comm | `Model` (from `@cositos/front`) over a `PlutoChannel` |
| kernel → view | `comm_msg` `update` | initial state embedded in HTML at render time |
| view → kernel | `comm_msg` `update` | `@bind`: `PlutoChannel` sets `element.value` + fires `input` |
| Julia value | traitlets | `@bind x widget` → `x` is the widget's full state `Dict` |

Because Pluto has no live kernel→frontend push mid-render, synchronization is **coarser**
than Jupyter: the frontend gets state once (at render), and every interaction publishes
the full state back to Julia via the bond (triggering reactive re-execution). Custom
messages (`model.send(...)`) have no kernel to reach and are routed to an optional sink.

## Julia side

`PlutoWidget` (core) + the `CositosPlutoExt` package extension (auto-loads with
`AbstractPlutoDingetjes` + `JSON`) provide the `Base.show` render and the `Bonds`
methods:

```julia
using Cositos, AbstractPlutoDingetjes    # extension activates

const SLIDER = raw"""
export default { render({ model, el }) {
  const i = document.createElement("input");
  i.type = "range"; i.min = model.get("min"); i.max = model.get("max");
  i.value = model.get("value");
  i.oninput = () => { model.set("value", +i.value); model.save_changes(); };
  el.appendChild(i);
}}
"""

@bind s PlutoWidget(esm=SLIDER, state=Dict("value"=>0, "min"=>0, "max"=>100))
# `s` reactively becomes Dict("value"=>…, "min"=>0, "max"=>100)
```

- `Bonds.initial_value(w) == w.state` — `s` starts as the full state.
- `Bonds.transform_value(w, from_js)` — Pluto transfers `element.value` (an object) as a
  `Dict`; used unchanged.

## Frontend side

`PlutoChannel` (from `@cositos/front`) is a `Channel` that treats the model's outbound
`update` as "publish full state to the bond": it merges partial updates, sets
`element.value`, and dispatches `input` — exactly what Pluto's `@bind` listens for.
`supports_receive = false`.

## Runtime hosting

The generated HTML `import`s `@cositos/front` from `runtime_url`. **You don't need to set
it.** `PlutoWidget`'s default (cositos-z76.7) resolves automatically to
[`Cositos.local_front_runtime_url()`](@ref) — a self-contained `data:` URI bundling
`front/src/*.js`, with **no npm publish, CDN, or local server required**, fully offline:

```julia
using Cositos, AbstractPlutoDingetjes, JSON   # extension activates

@bind s PlutoWidget(esm=SLIDER, state=Dict("value"=>0, "min"=>0, "max"=>100))
# nothing else to configure — runtime_url defaults to the local bundle.
```

Override `runtime_url` explicitly only if you want something else — e.g. a real CDN URL
once `@cositos/front` is published, or a self-hosted copy:

```julia
PlutoWidget(esm=SLIDER, state=..., runtime_url="https://cdn.jsdelivr.net/npm/@cositos/front/...")
```

This is what `examples/notebooks/pluto_demo.jl` uses, and was verified live end-to-end (a
real Pluto server + browser interaction: dragging the slider drove the `@bind`ed Julia
value through the locally-bundled runtime with no external resource). The bundling logic
assumes `front/src`'s import graph stays simple (currently one internal edge, `model.js`
depends on `buffers.js`); if a future file adds a new relative import, add it to the
bundle order in `CositosPlutoExt._bundle_front_source`.

## Status / caveats

- Verified by contract on both sides (JS: `front/test/pluto.test.js`; Julia:
  the Pluto testset in `julia/test/runtests.jl`), **and** live end-to-end against a real
  Pluto server + browser interaction (`examples/notebooks/pluto_demo.jl`, cositos-z76.7).
- Coarse reactive sync only; no `echo_update`, no binary buffers over the bond in v0
  (buffers work in the ESM locally but aren't round-tripped through `@bind`).
