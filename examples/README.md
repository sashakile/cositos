# cositos examples

Runnable demos of cositos widgets across hosts. See
`.wai/projects/cositos-core/designs/` for the integration design (live vs. static
rendering, and how these map to Voila / Quarto / JupyterBook / myBinder).

| Path | Host | Kernel? | Status |
|------|------|---------|--------|
| `web/index.html` | plain browser (`@cositos/front` + `LocalChannel`) | no | **works today** |
| `web/exported-widget-state.html` | static export of a saved `Document` via `embed_html` (CDN html-manager) | no (needs internet for the CDN) | **works today** |
| `static-export/` | notebook → static HTML via nbconvert; Quarto/JupyterBook recipes | no | nbconvert path **verified**; quarto/jb configs provided |
| `composition/` | a controls `VBox` composing two anywidget children in a static export | no | **works today** (run `build.py`; references resolve via a controls container) |
| `binder/` | live widgets on myBinder + Voila (kernel-backed) | yes | recipe (env + docs); live path is e2e-tested |
| `notebooks/python_counter.ipynb` | Jupyter (live comm via `CommTransport`) | yes | **works today** (needs `anywidget` in the frontend) |
| `parity/` | Julia port emits the same widget document as Python (drives the parity docs page) | no | **works today** (run `dump.jl`) |
| `widgets/*.js` | anywidget-style ESM used by the above and by tests | — | reference widgets |

## Backend-less web demo

```bash
cd examples          # ES module imports need HTTP, not file://
python3 -m http.server
# open http://localhost:8000/web/
```

The same ESM that runs in Jupyter renders here with no kernel; widget state lives in the
browser via `LocalChannel`.

## Live Jupyter notebook

Open `notebooks/python_counter.ipynb` in a JupyterLab/Notebook whose kernel can
`import cositos` and whose frontend has `anywidget` installed (cositos emits
`_model_module="anywidget"`, so the anywidget frontend renders it). Run all cells; click
**increment**; read `state['count']` back from the kernel.

## Static HTML export

Serialize any widgets to a `Document` and render a self-contained page — no kernel:

```python
from cositos import dump_document, write_html
doc = dump_document([("m", {"_esm": "export default {render({el}){el.textContent='hi'}}"})])
write_html("out.html", doc)   # open out.html in any browser (needs internet for the CDN)
```

`web/exported-widget-state.html` is a checked-in example produced this way from
`fixtures/widget-state.json`.

## Composing widgets (references)

A plain cositos widget is anywidget's `AnyModel`, which has no *widget-reference* traits,
so an `"IPY_MODEL_<id>"` string in its state stays a literal string on the frontend —
reference-based composition does **not** resolve against plain anywidget widgets. To
compose, emit a real `@jupyter-widgets/controls` container (a `VBoxModel` + companion
`LayoutModel` at module version `2.0.0`, not anywidget's `~0.11.*`) whose `children`
reference the anywidget children. `composition/build.py` is the runnable, browser-verified
recipe. Note: `jslink`/`dlink` (`LinkModel`) does **not** propagate in a backend-less
static export — linking needs a live kernel.

## Not yet

- **Pluto notebook** needs a Julia host adapter (the Julia port is protocol-core only).
