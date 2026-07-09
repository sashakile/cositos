# Research: Real `@jupyter-widgets/controls` models as an optional extension, not a core change

## Question

Given cositos' explicit anti-goal ("doesn't reimplement `@jupyter-widgets/controls`",
`docs/widgets.md`), and the fact that the ipywidgets *widget zoo* (`IntSlider`, `Dropdown`,
`VBox`, …) is currently Python-only (the `ipywidgets` package builds the traitlets model),
is there a way to reuse the **real** zoo frontend from any cositos host language,
without cloning it into JS and without adding Python-`ipywidgets`-shaped coupling to the
core?

## Method

Three checks, each isolating a different layer, run 2026-07-09:

1. **Wire-level override, no comm, no browser.** Call `cositos.protocol.build_comm_open`
   directly with a state dict carrying a real `@jupyter-widgets/controls` `IntSliderModel`
   identity (`_model_name`, `_model_module`, `_view_name`, …) instead of anywidget's
   defaults.
2. **Static render, real browser, no kernel.** Build a `Document` via
   `cositos.serialize.dump_document` with a `VBoxModel` (`@jupyter-widgets/controls`)
   containing an `IntSliderModel` and a `DropdownModel` (both with their required
   `LayoutModel`/`*StyleModel` companions), render via `cositos.embed.embed_html`, open in
   a real browser against the CDN `@jupyter-widgets/html-manager`.
3. **Live kernel, real comm.** Same `IntSliderModel` state dict, but through
   `cositos.jupyter.CommTransport` + `cositos.model.Widget.open()` against a **real,
   subprocess `ipykernel`** (the same harness as `tests/test_e2e_jupyter.py`), asserting
   the actual `comm_open` iopub message.

A fourth check isolated whether this needs the Python `ipywidgets` package at all: rebuilt
step 2 in a **fresh venv with `ipywidgets` and `anywidget` not installed** (`pip install -e
.` only, no extras).

A fifth check resolved an initial false alarm: a synthetic `MouseEvent`/`PointerEvent` drag
on the rendered slider's handle didn't change its value, initially misread as "real
controls widgets don't work locally without a kernel" (unlike anywidget's `AnyModel`, which
*does* update locally when clicked—verified side-by-side with the exact counter widget
from `docs/tutorials/static-export.qmd`). Driving the slider's own `noUiSlider` API
(`el.noUiSlider.set(77)`) instead of simulating a mouse drag **did** update the readout and
`aria-valuenow`, proving the model/view wiring is live and local exactly like anywidget's.
The synthetic-event drag simply wasn't recognized as a trusted gesture by the `noUiSlider`
library baked into `IntSliderView`; this is a test-harness limitation, not a limitation of
the widget or of cositos.

## Findings

1. **The core requires zero changes.** `build_comm_open`/`Widget.send_state` already do
   `{**anywidget_defaults, **state}`—state provided by the caller wins. A caller that
   supplies a full real-widget identity in its state dict gets that identity on the wire,
   today, with no branch, flag, or code path added to `src/cositos/protocol.py` or
   `src/cositos/model.py`.
2. **This holds over a real, live kernel comm, not just statically.** `Widget.open()`
   against a subprocess `ipykernel` (via `CommTransport`, the same transport
   `tests/test_e2e_jupyter.py` certifies) emitted a `comm_open` on the real iopub channel
   with `_model_module == "@jupyter-widgets/controls"`, `_model_name == "IntSliderModel"`,
   `_view_name == "IntSliderView"`, `value == 7`—that is, a real controls widget, live, driven
   entirely by cositos' existing `Widget`/`Transport`/`CommTransport`.
3. **No `ipywidgets` (or `anywidget`) Python package is required.** In a venv with neither
   installed, `cositos.serialize`/`cositos.embed` alone produce a `Document` that the CDN
   `html-manager` renders correctly as a real `VBoxModel` containing an `IntSliderModel`
   and `DropdownModel`. The *frontend* npm packages (`@jupyter-widgets/controls`/`base`)
   are the only runtime dependency, and they're already present wherever the anywidget
   frontend is (same assumption cositos already makes today).
4. **Real controls widgets behave identically to anywidget widgets when driven correctly:**
   local model/view sync with no kernel required (proven via the widget's own API, see
   Method #5). The earlier appearance of an asymmetry with anywidget's `AnyModel` was a
   synthetic-event recognition problem in the test, not a real behavioral difference.
5. **Not yet checked:** whether the pinned `@jupyter-widgets/controls@2.0.0` /
   `@jupyter-widgets/base@2.0.0` module versions used here (and already used by
   `examples/composition/build.py`) match what a real, currently-installed JupyterLab
   ships (only the CDN `html-manager` embed path and a subprocess `ipykernel`'s comm
   machinery were exercised—neither touches a real JupyterLab frontend's bundled
   `@jupyter-widgets` extension version). This is an open risk for the live-in-JupyterLab
   case specifically, not for the static-export or bare-comm cases just proven.

## Implication

"The zoo" doesn't need to be reimplemented per language (contradicting the earlier framing
in this session that treated it as a widget-cloning problem). It can be a **shared,
language-neutral catalog of real-controls model specs** (identity + default companion
models, keyed by widget name) plus a **thin per-language builder** that fills in overrides
and mints fresh companion-model ids per instance. Every host language that already has a
`Widget`/`Transport` pair (Python today; Julia's `ijulia_transport()` already exists) gets
real ipywidgets-frontend widgets for free—no new JS, no core change, no `ipywidgets`
Python dependency.

## Related

- Composition precedent this reuses: `examples/composition/build.py` (VBox + Layout,
  same `2.0.0` module-version choice).
- Contradicts nothing in `docs/widgets.md`'s anti-goal—that page targets *reimplementing*
  the zoo's frontend; this reuses the zoo's frontend verbatim, unmodified.
- Open item #5 above should be resolved (or explicitly accepted as a documented risk)
  before a live-JupyterLab tutorial ships using this pattern.
