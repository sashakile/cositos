# cositos examples

Runnable demos of cositos widgets across hosts. See
`.wai/projects/cositos-core/designs/` for the integration design (live vs. static
rendering, and how these map to Voila / Quarto / JupyterBook / myBinder).

| Path | Host | Kernel? | Status |
|------|------|---------|--------|
| `web/index.html` | plain browser (`@cositos/front` + `LocalChannel`) | no | **works today** |
| `web/exported-widget-state.html` | static export of a saved `Document` via `embed_html` (CDN html-manager) | no (needs internet for the CDN) | **works today** |
| `static-export/` | notebook → static HTML via nbconvert; Quarto/JupyterBook recipes | no | nbconvert path **verified**; quarto/jb configs provided |
| `notebooks/python_counter.ipynb` | Jupyter (live comm via `CommTransport`) | yes | **works today** (needs `anywidget` in the frontend) |
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

## Not yet

- **Quarto / JupyterBook** — the shared static-embed mechanism is verified via nbconvert
  in `static-export/` (with `_quarto.yml` / `_config.yml` starting points); neither tool
  is installed here to run end-to-end.
- **Pluto notebook** needs a Julia host adapter (the Julia port is protocol-core only).
