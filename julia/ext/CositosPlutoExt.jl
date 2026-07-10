"""
CositosPlutoExt — Pluto.jl integration for cositos.

Loads automatically when `AbstractPlutoDingetjes` and `JSON` are available. Provides:
- `Base.show(::MIME"text/html", ::PlutoWidget)` — renders the anywidget ESM via
  `@cositos/front`, wiring a `PlutoChannel` so the widget's container acts as an `@bind`
  target (Pluto reads `element.value` on `input` events).
- `Bonds.initial_value` / `Bonds.transform_value` — map the bound variable to/from the
  widget's full state `Dict`.
- `Cositos.local_front_runtime_url()` — a `data:` URI bundling `@cositos/front` with no
  npm publish, CDN, or local server required (cositos-z76.7).

Pluto is reactive-cell-based, not a live comm: state flows Julia→JS once at render time
(embedded in the HTML) and JS→Julia via the bond on each interaction. There is no
mid-render kernel push, so continuous fine-grained sync (as in Jupyter) is coarser here.
"""
module CositosPlutoExt

using Cositos: Cositos, PlutoWidget
using AbstractPlutoDingetjes
import JSON
using Base64: base64encode

# ---- local, offline runtime bundling (cositos-z76.7) ----
#
# @cositos/front (front/src/*.js) is not published to npm/CDN yet. Rather than block
# Pluto usage on that, this bundles the SAME source the JS test suite certifies
# (front/test/*.test.js) into one self-contained ESM — no relative imports left — and
# hands it back as a `data:` URI: no server, no network, no npm required.
#
# The import graph is trivial (checked live against front/src, 2026-07: index.js just
# re-exports Model/channels/runtime; the only internal edge is model.js importing
# remove_buffers/put_buffers from buffers.js), so a plain concatenation in dependency
# order, with that one import line stripped, is a correct, dependency-free bundle — no
# bundler tool needed. If a future front/src file grows a new internal import, this
# bundling breaks loudly (Cositos.local_front_runtime_url()'s test asserts the output
# has zero remaining `import` statements), not silently.
const _FRONT_SRC_DIR = joinpath(@__DIR__, "..", "..", "front", "src")

function _bundle_front_source()
    buffers_js = read(joinpath(_FRONT_SRC_DIR, "buffers.js"), String)
    channels_js = read(joinpath(_FRONT_SRC_DIR, "channels.js"), String)
    runtime_js = read(joinpath(_FRONT_SRC_DIR, "runtime.js"), String)
    model_js = read(joinpath(_FRONT_SRC_DIR, "model.js"), String)
    # model.js's only internal import: now inlined above it in the same module scope.
    model_js = replace(model_js, r"^import \{[^}]*\} from \"\./buffers\.js\";\n"m => "")
    return join([buffers_js, channels_js, runtime_js, model_js], "\n")
end

function Cositos.local_front_runtime_url()
    bundle = _bundle_front_source()
    return "data:text/javascript;base64,$(base64encode(bundle))"
end

function Base.show(io::IO, ::MIME"text/html", w::PlutoWidget)
    # runtime_url left at its DEFAULT_RUNTIME_URL sentinel auto-resolves to the local,
    # offline bundle -- the common case needs no separate call to
    # Cositos.local_front_runtime_url() (cositos-z76.7 UX follow-up). An explicit,
    # different runtime_url (e.g. a real published CDN URL, or a self-hosted copy) is
    # respected verbatim.
    effective_url = w.runtime_url == Cositos.DEFAULT_RUNTIME_URL ? Cositos.local_front_runtime_url() : w.runtime_url
    url = JSON.json(effective_url)
    state = JSON.json(w.state)
    esm = JSON.json(w.esm)
    css = JSON.json(w.css)
    print(
        io,
        """
        <div>
        <script>
        const container = document.currentScript.parentElement;
        (async () => {
          const { Model, PlutoChannel, loadWidget, renderWidget } = await import($(url));
          const state = $(state);
          const esm = $(esm);
          const css = $(css);
          if (css) { const s = document.createElement("style"); s.textContent = css; container.appendChild(s); }
          const channel = new PlutoChannel(container, state);
          const model = new Model(state, channel);
          const view = document.createElement("div");
          container.appendChild(view);
          await renderWidget(await loadWidget(esm), { model, el: view });
        })();
        </script>
        </div>
        """,
    )
    return nothing
end

# The bound variable is the widget's full state Dict (post-transform).
AbstractPlutoDingetjes.Bonds.initial_value(w::PlutoWidget) = w.state

# Pluto transfers the JS `element.value` object as a Dict; use it unchanged.
AbstractPlutoDingetjes.Bonds.transform_value(::PlutoWidget, from_js) = from_js

end # module
