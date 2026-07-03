# Widgets: covering the ipywidgets surface without cloning the zoo

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

## "But I want the actual ipywidgets widgets"

Then use ipywidgets — it's installed alongside and speaks the same comm protocol. cositos
is the *build-your-own* path: when you need a bespoke widget (a d3 chart, a custom form, a
WASM-backed control), you write ESM instead of a new Python/JS widget class pair.
