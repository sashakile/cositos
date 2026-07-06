# Static export → Quarto / JupyterBook / nbconvert

Render a notebook containing a **cositos** widget to static HTML with **no running
kernel**. All three tools below share one mechanism, so this folder verifies that
mechanism once (via `nbconvert`) and documents how each tool consumes it.

## The shared mechanism

A widget is embedded statically by two pieces of data:

1. The widget cell's **output** is a `application/vnd.jupyter.widget-view+json` mimebundle
   (carrying the `model_id`). cositos emits this via `Widget._repr_mimebundle_`, so simply
   displaying the widget in a cell produces it.
2. The **notebook metadata** carries the widget-state `Document` at
   `metadata.widgets["application/vnd.jupyter.widget-state+json"]`. A static builder reads
   this to reconstruct the models, then the CDN-hosted `@jupyter-widgets/html-manager`
   renders each view.

**cositos caveat:** ordinary ipywidgets writes piece 2 automatically because its widgets
register with a widget manager on save. cositos is binding-free and does **not**, so you
must inject the `Document` yourself after building/executing the notebook. `build.py`'s
`inject_widget_state(nb, dump_document(entries))` shows the one-liner.

## Verified path: nbconvert

`build.py` constructs such a notebook and exports it. This is exercised by
`tests/test_static_export.py` (opt-in — needs the `export` extra):

```bash
uv run --extra dev --extra export pytest tests/test_static_export.py
uv run --extra dev --extra export python examples/static-export/build.py
# → writes counter.html (gitignored; open in any browser, needs internet for the CDN)
```

JupyterBook builds on nbconvert, so the same embedded `metadata.widgets` block flows
through `jupyter-book build`.

## Quarto and JupyterBook configs

Both are provided as minimal starting points. **They rest on the verified nbconvert
mechanism above but were not executed in this environment** (neither `quarto` nor
`jupyter-book` is installed here). The load-bearing part — that a cositos widget embeds
from the `metadata.widgets` state block — is what the nbconvert test proves.

- `quarto/_quarto.yml` + `quarto/counter.qmd` — Quarto reads the same
  `application/vnd.jupyter.widget-state+json` block. Render with `quarto render quarto/`.
  Because cositos doesn't auto-write that block, execute the notebook then inject the
  Document (as in `build.py`) before `quarto render`, or embed a pre-built
  `metadata.widgets` in the `.qmd` front matter.
- `jupyterbook/_config.yml` + `jupyterbook/_toc.yml` — set
  `execute.execute_notebooks: cache` and include a notebook whose `metadata.widgets` has
  been injected. Build with `jupyter-book build jupyterbook/`.

## The simpler alternative

If you only need a standalone page (not a Quarto/JupyterBook site), skip all of this and
use `cositos.embed.write_html(path, dump_document(entries))` — a lean self-contained page
with no notebook toolchain. See `../web/exported-widget-state.html`.
