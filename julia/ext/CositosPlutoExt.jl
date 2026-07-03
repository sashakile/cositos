"""
CositosPlutoExt — Pluto.jl integration for cositos.

Loads automatically when `AbstractPlutoDingetjes` and `JSON` are available. Provides:
- `Base.show(::MIME"text/html", ::PlutoWidget)` — renders the anywidget ESM via
  `@cositos/front`, wiring a `PlutoChannel` so the widget's container acts as an `@bind`
  target (Pluto reads `element.value` on `input` events).
- `Bonds.initial_value` / `Bonds.transform_value` — map the bound variable to/from the
  widget's full state `Dict`.

Pluto is reactive-cell-based, not a live comm: state flows Julia→JS once at render time
(embedded in the HTML) and JS→Julia via the bond on each interaction. There is no
mid-render kernel push, so continuous fine-grained sync (as in Jupyter) is coarser here.
"""
module CositosPlutoExt

using Cositos: Cositos, PlutoWidget
using AbstractPlutoDingetjes
import JSON

function Base.show(io::IO, ::MIME"text/html", w::PlutoWidget)
    url = JSON.json(w.runtime_url)
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
