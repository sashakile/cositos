## Why

Widgets serialized with `serialize-widget-state` are just data; to *view* a saved UI
without a running kernel you need a self-contained HTML file. ipywidgets already defines
this embed format (`embed_minimal_html`): a `application/vnd.jupyter.widget-state+json`
block plus per-view `widget-view+json` scripts, rendered by the CDN-hosted
`@jupyter-widgets/html-manager`. Since cositos already produces that exact state schema
and reuses the anywidget frontend (resolvable from jsDelivr), a thin embed helper unlocks
static export for nbconvert, Quarto, and JupyterBook in one place.

## What Changes

- Add an `embed` capability: `embed_html(document, *, views=None, title=..., requirejs=True,
  html_manager_version="1") -> str` and `write_html(path, document, **kwargs)`.
- The embedded state block is the `Document` produced by `dump_document` (schema v2),
  script-escaped per the HTML spec.
- Per-view `widget-view+json` scripts are emitted for the requested `views` (default: all
  model ids in the document).
- The CDN loader references `@jupyter-widgets/html-manager` (embed-amd.js + require.js);
  the anywidget model/view module resolves from jsDelivr at render time.

### Non-goals

- Executing/serializing live widgets (that is the host's job via `dump_document`).
- A bespoke widget manager or bundling the frontend locally (reuse the stock CDN manager).
- nbconvert/Quarto/JupyterBook recipe files (separate ticket `cositos-z76.4`).

## Capabilities

### New Capabilities
- `embed`: render a serialized widget `Document` into a self-contained static HTML page
  using the stock ipywidgets html-manager and CDN-hosted frontend modules.

### Modified Capabilities
<!-- None. Additive; consumes the serialization capability's output. -->

## Impact

- **Code:** new `src/cositos/embed.py`; re-export from `src/cositos/__init__.py`.
- **Depends on:** `serialization` (`dump_document` output is the embed input).
- **External:** render correctness relies on jsDelivr serving
  `@jupyter-widgets/html-manager` and `anywidget` (reachability verified: HTTP 200).
- **Dependencies:** none new (`json`, `html` are stdlib).
