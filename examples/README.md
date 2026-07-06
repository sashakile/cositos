# cositos examples

Runnable demos of cositos widgets across hosts. See
`.wai/projects/cositos-core/designs/` for the integration design (live vs. static
rendering, and how these map to Voila / Quarto / JupyterBook / myBinder).

| Path | Host | Kernel? | Status |
|------|------|---------|--------|
| `web/index.html` | plain browser (`@cositos/front` + `LocalChannel`) | no | **works today** |
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

## Not yet

- **Static HTML export** (and therefore Quarto / JupyterBook / nbconvert) is blocked on
  the `serialize-widget-state` change plus an `embed` helper — see the integration design.
- **Pluto notebook** needs a Julia host adapter (the Julia port is protocol-core only).
