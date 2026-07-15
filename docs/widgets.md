---
title: "Widgets: covering the ipywidgets surface without cloning the zoo"
---

> **What this page is:** The six ipywidgets categories cositos can express — value
> types, ESM patterns, and per-language code snippets.

A cositos widget is an anywidget-compatible ES module — a small JavaScript file that
renders a UI element and syncs state over a Jupyter comm channel. This page catalogs the
ipywidgets categories cositos can express. See [Authoring a widget](tutorials/authoring-widgets.qmd)
for how to write one from scratch, or the [Widget gallery](widgets-gallery.qmd) for live demos.

> **What this page is:** The six ipywidgets categories cositos can express — value
> types, ESM patterns, and per-language code snippets.

**cositos does not reimplement `@jupyter-widgets/controls`.** ipywidgets ships ~30
frontend widget classes (`IntSlider`, `Button`, `Dropdown`, …); cloning them verbatim
would be large and pointless. The whole premise of the anywidget/cositos model is that
**one `AnyModel` + a few lines of ESM express any widget**, and cositos widgets speak the
exact same protocol, so they **coexist with real ipywidgets** in the same notebook.

## Category coverage (proven)

`examples/widgets/` holds plain anywidget-style ESM — unchanged, they run in Jupyter via
the ipywidgets frontend *and* under `@cositos/front` (web / WASM / Pluto). Each maps to an
ipywidgets category and is render+interaction tested in `front/test/gallery.test.js`:

| Category | ipywidgets examples | cositos example | How state flows |
|---|---|---|---|
| Numeric | IntSlider, FloatSlider | `int_slider.js` | `value` two-way |
| Boolean | Checkbox, ToggleButton | `checkbox.js` | `value` two-way |
| String | Text, Textarea | `text.js` | `value` two-way |
| Button/event | Button | `button.js` | `clicks` state + `custom` event |
| Selection | Dropdown, Select, RadioButtons | `dropdown.js` | `value` + `options` |
| Output/display | HTML, Label, Output | `html.js` | `value` (kernel → view) |

These six exercise every synchronization pattern the protocol supports: two-way state,
kernel→view push, dynamic option lists, and custom event messages. Anything else in
ipywidgets is a variation on these — no new machinery required.

**Want to see each one running, plus the snippet that launches it per language?**
[`docs/widgets-gallery.qmd`](widgets-gallery.qmd) has a live, in-browser demo of every
widget in the table above, next to the Python/Julia code that launches it for real.

## "But I want the actual ipywidgets widgets"

Then use ipywidgets — it's installed alongside and speaks the same comm protocol. cositos
is the *build-your-own* path: when you need a bespoke widget (a d3 chart, a custom form, a
WASM-backed control), you write ESM instead of a new Python/JS widget class pair.

## Reusing a real ipywidgets control instead of building one

Sometimes you don't want to build a widget at all — you want the *real*
`IntSlider`/`Dropdown`/`VBox` frontend, unmodified, without installing the `ipywidgets`
Python package. `cositos.contrib.controls` provides exactly that: a small, optional
catalog that builds state for the real `@jupyter-widgets/controls`/`base` frontend
directly, with no `ipywidgets` (or `anywidget`) Python dependency.

This works with **zero changes to cositos' core**: the wire-level builder
(`build_comm_open`/`Widget.send_state`) already merges `{**anywidget_defaults, **state}`,
so a caller that supplies a real widget's own identity
(`_model_name`/`_model_module`/`_view_name`/`_view_module`, etc.) gets that identity on
the wire as-is — the core never distinguishes an anywidget-authored widget from a real
ipywidgets one.

See [`docs/widgets-gallery.qmd`](widgets-gallery.qmd#real-ipywidgets-controls-no-reimplementation-required)
for a runnable example (`int_slider()`, `dropdown()`, `vbox()`) built from
`cositos.contrib.controls` — unlike [`cositos.contrib.harvest`](tutorials/plot-integration.qmd#about-cositos.contrib),
this one needs neither `ipywidgets` nor `anywidget` installed.

For the full scenario—building a small dashboard from these real controls, downloading its state, and restoring it in a fresh session—see [`tutorials/dashboard.qmd`](tutorials/dashboard.qmd).
