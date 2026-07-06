# Design: notebooks, static-HTML export, and integration with Voila / Quarto / JupyterBook / myBinder

## Context
cositos widgets render live in Jupyter today (proven by the real-kernel e2e test). Users
also want (a) example notebooks per host language, (b) to export a notebook to **static
HTML**, and (c) to know how cositos fits **Voila, Quarto, JupyterBook, and myBinder**.
This note grounds those in the existing machinery and identifies exactly what must be
built versus what already works.

## The one distinction that organises everything: live vs. static

Every widget-rendering context is exactly one of:

- **Live** — a kernel is running; the frontend talks to it over the Jupyter **comm**
  channel (real two-way messages). cositos already supports this via `CommTransport`.
- **Static** — no kernel. The widget's state is **embedded in the HTML** as a
  `application/vnd.jupyter.widget-state+json` block, and the frontend module is loaded
  from a CDN. Nothing can change after page load unless the widget's own ESM does it
  client-side.

Mapping the four tools:

| Tool | Mode | Needs from cositos |
|------|------|--------------------|
| **Voila** | live | serves a notebook with a running kernel; renders widgets via their mimebundle. Needs a working display hook. |
| **myBinder** | live | a reproducible Docker env (repo + `environment.yml`/`requirements.txt`) that launches a kernel. Needs the same display hook + an installable package. |
| **nbconvert `--to html --embed-images`/`--embed-widget-state`** | static | serialize the live widgets to `widget-state+json` and embed them. |
| **Quarto** | static | consumes the same `widget-state+json` that Jupyter emits into cell outputs on execute. |
| **JupyterBook** | static | builds static HTML via nbconvert/MyST; embeds the same `widget-state+json`. |

**Consequence:** static export for nbconvert, Quarto, and JupyterBook is **one feature**,
not three — they all consume the same embedded state block. And Voila + myBinder are **one
enabler** — a working display hook — plus packaging.

## Grounding in existing machinery

- ipywidgets already ships static export: `embed_minimal_html(fp, views, ...)`,
  `embed_data`, and `dependency_state` in `ipywidgets/.../embed.py`. `embed_snippet`
  writes two things into the HTML: a `require.js`/CDN loader for the frontend manager
  (`@jupyter-widgets/html-manager`) and a `<script
  type="application/vnd.jupyter.widget-state+json">` block — which is **exactly** the v2
  schema our `serialize-widget-state` change (`cositos-zi8`) produces.
- The frontend module for a cositos widget is anywidget's published `AnyModel`/`AnyView`.
  For static embedding the html-manager must resolve `_model_module="anywidget"` from a
  CDN (jsDelivr). **Unverified** — must be tested; it is the load-bearing assumption for
  all static export.

## Two gaps this exposes in the current core

1. **No `_repr_mimebundle_`.** `Widget` exposes `mimebundle()` but not the dunder Jupyter
   calls to display an object. `jupyter.py`'s docstring even *claims* "display via
   `_repr_mimebundle_`," but it is not implemented. So live display currently requires an
   explicit `display(widget.mimebundle(), raw=True)`. A small `_repr_mimebundle_` shim on
   `Widget` unblocks **all three live contexts** (Jupyter, Voila, myBinder) at once and
   makes `widget` render as a bare last-line expression.
2. **No static-export helper.** There is no cositos equivalent of `embed_minimal_html`.
   It is a thin layer over `serialize-widget-state`: take the document, wrap it in the
   embed HTML template with the CDN loader. Depends on the serialize epic.

## What works today (no new code)

- **Backend-less web** — `@cositos/front` (`Model` + `LocalChannel` + `loadWidget` /
  `renderWidget`) renders any anywidget ESM in a plain browser with no kernel. Shipped as
  `examples/web/index.html` (smoke-verified via jsdom).
- **Live Python notebook** — `CommTransport` + `display(widget.mimebundle(), raw=True)`.
  Shipped as `examples/notebooks/python_counter.ipynb`. Requires a running kernel with
  `cositos` importable and `anywidget` installed in the frontend.

## What is blocked, and on what

- **Pluto notebook** — blocked: the Julia side is protocol-core only (no IJulia/Pluto
  host adapter), and Pluto rendering needs the `@cositos/front` ESM served into the
  notebook. Needs Julia host plumbing + a published/inlined front bundle.
- **Static HTML export** (and therefore Quarto / JupyterBook / nbconvert) — blocked on
  `serialize-widget-state` (`cositos-zi8`) + a new `embed` helper + verifying anywidget
  loads from a CDN.
- **Voila / myBinder** — need the `_repr_mimebundle_` shim (small) + packaging
  (`environment.yml`, a Binder-ready repo). Live rendering otherwise already works.

## Recommended sequencing
1. `_repr_mimebundle_` display shim on `Widget` (small; unblocks Voila/Binder/plain
   Jupyter ergonomics). *Own ticket, TDD.*
2. Finish `serialize-widget-state` (`cositos-zi8`).
3. `embed` capability: `embed_html(document) -> str` / `write_html(path, document)` +
   verify anywidget CDN resolution. *New OpenSpec change, depends on 2.*
4. Recipes on top of 3: nbconvert post-processor, Quarto `_quarto.yml` example,
   JupyterBook `_config.yml` example, myBinder `environment.yml` + a Binder badge.
5. Julia/Pluto host adapter + Pluto demo notebook. *Separate track.*

## Non-goals (now)
Cloning `@jupyter-widgets/controls`; a bespoke widget manager; server-side rendering of
arbitrary ESM. Static export deliberately reuses the stock html-manager + CDN modules.

