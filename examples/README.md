# cositos examples

Runnable demos of cositos widgets across hosts. New to cositos? Start with
[`docs/tutorials/quickstart.qmd`](../docs/tutorials/quickstart.qmd) for the shortest
runnable snippet per language before diving into these. See
`.wai/projects/cositos-core/designs/` for the integration design (live vs. static
rendering, and how these map to Voila / Quarto / JupyterBook / myBinder).

| Path | Host | Kernel? | Status |
|------|------|---------|--------|
| `web/index.html` | plain browser (`@cositos/front` + `LocalChannel`) | no | **works today** |
| `web/exported-widget-state.html` | static export of a saved `Document` via `embed_html` (CDN html-manager) | no (needs internet for the CDN) | **loads cleanly, renders BLANK by design** (see note below) |
| `static-export/` | notebook → static HTML via nbconvert; Quarto/JupyterBook recipes | no | nbconvert path **verified**; quarto/jb configs provided |
| `composition/` | a controls `VBox` composing two anywidget children in a static export | no | **works today** (run `build.py`; references resolve via a controls container) |
| `dashboard/` | real `IntSlider`+`Dropdown` (`cositos.contrib.controls`) driving an anywidget summary via one MVU host Model, composed in a real `VBox` | no for the static snapshot; yes for live dispatch | **works today** (run `build.py`; live-kernel wiring e2e-tested) |
| `plots/` | harvest an existing Plotly `FigureWidget` into a static export via `cositos.contrib.harvest` | no | **works today** (`uv run --with plotly python examples/plots/build.py`) |
| `binder/` | live widgets on myBinder + Voila (kernel-backed) | yes | recipe (env + docs); live path is e2e-tested |
| `notebooks/python_counter.ipynb` | Jupyter (live comm via `CommTransport`) | yes | **works today** (needs `anywidget` in the frontend) |
| `notebooks/julia_counter.ipynb` | IJulia (live comm via `CositosIJuliaExt`) | yes | **works today** (Cositos-enabled IJulia kernel + `anywidget` in the frontend) |
| `parity/` | Julia port emits the same widget document as Python (drives the parity docs page) | no | **works today** (run `dump.jl`) |
| `widgets/*.js` | anywidget-style ESM used by the above and by tests | — | reference widgets |

## Backend-less web demo

```bash
# Serve from the repo root, not examples/: index.html imports the frontend via
# ../../front/src/index.js, which only resolves if front/ (a sibling of examples/ at
# the repo root) is inside the served tree (cositos-0e8).
python3 -m http.server 8000     # run from the repo root; ES module imports need HTTP, not file://
# open http://localhost:8000/examples/web/
```

The same ESM that runs in Jupyter renders here with no kernel; widget state lives in the
browser via `LocalChannel`.

## Live Jupyter notebook

Open `notebooks/python_counter.ipynb` in a JupyterLab/Notebook whose kernel can
`import cositos` and whose frontend has `anywidget` installed (cositos emits
`_model_module="anywidget"`, so the anywidget frontend renders it). Run all cells; click
**increment**; read `state['count']` back from the kernel.

`notebooks/julia_counter.ipynb` is the Julia twin: the same counter over IJulia's comm via
the `CositosIJuliaExt` extension. It needs an IJulia kernel bound to a project where
`Cositos` and `IJulia` are available (see the notebook's prerequisites). The live
round-trip is covered automatically by `tests/test_e2e_julia.py` (`mise run e2e`).

## Static HTML export

Serialize any widgets to a `Document` and render a self-contained page — no kernel:

```python
from cositos import dump_document, write_html
doc = dump_document([("m", {"_esm": "export default {render({el}){el.textContent='hi'}}"})])
write_html("out.html", doc)   # open out.html in any browser (needs internet for the CDN)
```

`web/exported-widget-state.html` is a checked-in example produced this way from
`fixtures/widget-state.json`.

**Why it renders a blank page (intentional, cositos-mbp):** `fixtures/widget-state.json`
is the cross-language *golden serialization fixture* -- Python, Julia, R, C#, and Clojure
all certify their `dump_document`/`load_document` against this exact file (see
`examples/parity/README.md`), so its two widgets' `_esm` strings are comment-only
placeholders (`/* VBox */`, `/* float32 plot */`) reused verbatim across every port's test
suite. Editing them here would require updating five other languages' test fixtures for
no serialization benefit, so we don't. `mise run qa-export` only checks that the export
*loads* (CDN scripts 200, no console errors, no `jupyter-widgets-error-widget`) -- for a
static export that actually **renders** something, open `composition/vbox.html` (`mise run
qa-composition`) instead.

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

- **Pluto notebook** uses the Julia `PlutoWidget` host (`CositosPlutoExt`); a runnable
  Pluto example is not yet checked in.
