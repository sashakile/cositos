# Design: Controls-catalog schema + scope (Slider/Dropdown/VBox+HBox only)

## Goal

Give ticket `cositos-70b.2` (the fixtures + Python builder) a schema to fill in, so it
doesn't have to invent one or copy the research probe's hardcoded ids. Scope is trimmed
to exactly what the dashboard example (`cositos-70b.4`) consumes.

## Grounding: Don't Reimplement, Don't Guess Module Versions

- `claim:01KX3KD9D0KJEB4469MGBZ9E21` ("real controls models work as an optional
  extension, zero core changes") and
  `.wai/projects/cositos-core/research/2026-07-09-research-real-controls-widgets-as-optional-extension.md`
  establish that `build_comm_open`/`Widget.send_state` already do
  `{**anywidget_defaults, **state}`—a caller supplying a full real-widget identity
  gets it on the wire today, no core change. This design only decides *what shape* that
  caller-supplied state takes when it's the real controls zoo.
- Module identities and default trait values below are read directly from the vendored
  `ipywidgets` source (read-only reference repo at `../ipywidgets`, not modified per
  workspace `AGENTS.md`):
  `python/ipywidgets/ipywidgets/widgets/widget_int.py`,
  `widget_selection.py`, `widget_box.py`, `widget_layout.py`, `widget_description.py`,
  `widget_core.py`. This avoids inventing defaults that drift from the real frontend.
- Module version `2.0.0` for `@jupyter-widgets/controls` and `@jupyter-widgets/base` is
  the same choice already made by `examples/composition/build.py` (precedent, not a new
  decision)—`_IPYWIDGETS_VERSION = "2.0.0"` there.

## Scope (trimmed, YAGNI)

Catalog this pass:

| Catalog key | `model_name` | `view_name` | Module |
|---|---|---|---|
| `int_slider` | `IntSliderModel` | `IntSliderView` | `@jupyter-widgets/controls` |
| `dropdown` | `DropdownModel` | `DropdownView` | `@jupyter-widgets/controls` |
| `vbox` | `VBoxModel` | `VBoxView` | `@jupyter-widgets/controls` |
| `hbox` | `HBoxModel` | `HBoxView` | `@jupyter-widgets/controls` |

Required companion models (no view of their own—`view_name: null`):

| Companion | `model_name` | Module | Used by |
|---|---|---|---|
| layout | `LayoutModel` | `@jupyter-widgets/base` | every widget above (`layout` trait) |
| slider_style | `SliderStyleModel` | `@jupyter-widgets/controls` | `int_slider` (`style` trait) |
| description_style | `DescriptionStyleModel` | `@jupyter-widgets/controls` | `dropdown` (`style` trait)—`Dropdown` is a `DescriptionWidget` |

Explicitly **not** cataloged this pass (no consumer yet—open a follow-up ticket if one
appears): `Checkbox`, `Text`, `Button`, `Tab`, `Accordion`, `BoundedIntText`,
`RadioButtons`, `Select*`.

## Catalog schema

JSON, keyed by widget name (the catalog keys in the table above), one object per entry:

```json
{
  "int_slider": {
    "model_name": "IntSliderModel",
    "model_module": "@jupyter-widgets/controls",
    "model_module_version": "2.0.0",
    "view_name": "IntSliderView",
    "view_module": "@jupyter-widgets/controls",
    "view_module_version": "2.0.0",
    "default_state": {
      "value": 0,
      "min": 0,
      "max": 100,
      "step": 1,
      "orientation": "horizontal",
      "readout": true,
      "readout_format": "d",
      "continuous_update": true,
      "disabled": false,
      "behavior": "drag-tap",
      "description": "",
      "style": "IPY_MODEL_<slider_style_id>",
      "layout": "IPY_MODEL_<layout_id>"
    },
    "companions": [
      {
        "key_in_default_state": "style",
        "model_name": "SliderStyleModel",
        "model_module": "@jupyter-widgets/controls",
        "view_name": null,
        "view_module": "@jupyter-widgets/controls"
      },
      {
        "key_in_default_state": "layout",
        "model_name": "LayoutModel",
        "model_module": "@jupyter-widgets/base",
        "view_name": null,
        "view_module": "@jupyter-widgets/base"
      }
    ]
  }
}
```

Field meaning, all fields required except `companions` (empty list if none):

- `model_name` / `model_module` / `model_module_version`: written verbatim to
  `_model_name` / `_model_module` / `_model_module_version` in the built state dict.
- `view_name` / `view_module` / `view_module_version`: written to `_view_name` /
  `_view_module` / `_view_module_version`. `view_name: null` for view-less companions
  (`LayoutModel`, `*StyleModel`—matches `examples/composition/build.py`'s
  `LayoutModel` entry, which sets `"_view_name": None`).
- `default_state`: the trait defaults read from the ipywidgets source, **as literal
  values**—except reference-valued traits (`style`, `layout`, `children` for
  `vbox`/`hbox`), which hold the placeholder string
  `"IPY_MODEL_<companion-role>_id"`. The builder (ticket 2) replaces every such
  placeholder with a freshly minted `model_id` before emitting the entry—see
  "Id-uniqueness rule" below. The catalog itself is never fed to `dump_document`
  directly.
- `companions`: one entry per reference-valued key in `default_state`, naming which
  companion model/view fills that key. `key_in_default_state` must match a key present
  in `default_state` whose value is a placeholder string. `vbox`/`hbox` additionally
  have a `children` key holding a *list* of placeholders (one per child slot the builder
  fills at call time—not a fixed companion, so it's documented in prose here rather
  than a `companions` entry): `"children": ["IPY_MODEL_<child_1>", "IPY_MODEL_<child_2>", ...]`.

## Id-uniqueness rule (must-fix #2)

**The builder MUST mint a fresh, unique `model_id` for every companion model on every
call**—for example `uuid4()`, or a caller-supplied prefix combined with the companion role
(`f"{prefix}-layout"`, `f"{prefix}-style"`). It must **never** reuse the catalog's
literal placeholder strings (`IPY_MODEL_<slider_style_id>` etc. above) as real
ids—those are schema documentation, not usable ids.

This is required because `dump_document` treats `model_id` as the primary key of the
document (`.wai/projects/cositos-core/designs/2026-07-06-design-serializable-widgets-composition-and-a.md`,
"model_id is the primary key—validate at the boundary") and **rejects duplicate
`model_id`s** when building a `Document`. Two dashboard widgets built from the same
catalog entry (for example two `int_slider`s) each need their own `LayoutModel`/`SliderStyleModel`
companion instances with distinct ids—reusing a literal id across instances would
either collide (rejected) or silently make two widgets share one companion's state.

Concretely, the builder's per-call responsibility (owned by ticket `cositos-70b.2`, not
improvised there—stated here so it isn't skipped):

1. For each catalog entry requested, mint one fresh id for the widget itself and one
   fresh id per companion in `companions` (plus one per child slot for `vbox`/`hbox`).
2. Substitute every `IPY_MODEL_<placeholder>` in `default_state`/`children` with the
   corresponding freshly minted id, prefixed `IPY_MODEL_` as `dump_document`/
   `load_document` expect (matches `examples/composition/build.py`'s `"IPY_MODEL_child_a"`
   convention).
3. Apply caller overrides (for example `value=50`, `options=[...]`) on top of the substituted
   `default_state` before emitting the `ModelEntry` tuple
   (`(model_id, {**catalog_state, **overrides})`—same override pattern the research
   doc confirms for `Widget.send_state`).

## Full default_state per catalog entry

Read directly from the vendored ipywidgets source cited above (traits with no explicit
default fall back to their trait type's zero value, for example `Bool()` -> `False`,
`Unicode()` -> `""`):

- **`int_slider`** (`_BoundedInt`/`IntSlider`, `widget_int.py`): `value=0`, `min=0`,
  `max=100`, `step=1`, `orientation="horizontal"`, `readout=true`,
  `readout_format="d"`, `continuous_update=true`, `disabled=false`,
  `behavior="drag-tap"`, `description=""`, `description_allow_html=false`,
  `style=IPY_MODEL_<slider_style_id>`, `layout=IPY_MODEL_<layout_id>`.
- **`dropdown`** (`_Selection`/`Dropdown`, `widget_selection.py` +
  `widget_description.py`): `_options_labels=[]`, `index=null`, `disabled=false`,
  `description=""`, `description_allow_html=false`,
  `style=IPY_MODEL_<description_style_id>`, `layout=IPY_MODEL_<layout_id>`.
  **Correction found empirically in `cositos-70b.2`'s real-browser check** (not visible
  from the trait names alone without checking `.tag(sync=True)`): `_Selection`'s
  `options`, `value`, and `label` traits carry **no** `sync=True` tag in ipywidgets—only
  `_options_labels` (label strings) and `index` are ever on the wire. A first catalog
  draft that put `options=[...]`/`value=...` straight into `default_state` built and
  serialized without error, but rendered an **empty, unselectable** `<select>` in a real
  browser (confirmed via the `chrome-dev-tools` skill, then via source:
  `widget_selection.py` declares `options = Any((), ...)` and `value = Any(None, ...)`
  with no `.tag(sync=True)` at all). The builder (ticket 2) exposes ergonomic
  `options=`/`value=` parameters but translates them to `_options_labels`/`index` before
  they reach `default_state`. The builder is expected to always override
  `_options_labels` (and typically `index`) since an empty-options dropdown has nothing
  to select—that's a caller override, not a catalog default change.
- **`vbox`** / **`hbox`** (`Box`/`VBox`/`HBox`, `widget_box.py`): `children=[]`,
  `box_style=""`, `layout=IPY_MODEL_<layout_id>`. `children` is populated by the
  builder from the child widgets passed in, as a list of `IPY_MODEL_<child_id>`
  strings (matches `examples/composition/build.py`'s `"children": ["IPY_MODEL_child_a",
  "IPY_MODEL_child_b"]`)—it's not a fixed-arity companion, so it has no fixed
  placeholder count in the catalog entry itself.
- **`layout`** companion (`LayoutModel`, `widget_layout.py`): all traits optional/None
  by default (width, height, border, margin, padding, display, etc.)—the catalog's
  `default_state` for the `layout` companion is `{}` (an empty object); callers override
  individual layout traits as needed, matching `examples/composition/build.py`'s bare
  `LayoutModel` entry (no extra state beyond the four identity fields).
- **`slider_style`** companion (`SliderStyleModel`, `widget_int.py`): `handle_color=null`
  plus inherited `description_width=""` (from `DescriptionStyle`)—default_state `{}`.
- **`description_style`** companion (`DescriptionStyleModel`, `widget_description.py`):
  `description_width=""`—default_state `{}`.

## Non-goals of this note

- Doesn't implement the builder (`src/cositos/contrib/controls.py`) or the fixture
  file—that's `cositos-70b.2`.
- Doesn't decide the dashboard's MVU wiring—that's `cositos-70b.4`.
- Doesn't re-verify the open risk from the research doc (module-version match against a
  real, currently-installed JupyterLab)—still an accepted, documented risk for the
  live-JupyterLab case.

## Reviewed against

`claim:01KX3KD9D0KJEB4469MGBZ9E21`—this note's catalog shape is a direct, literal
encoding of what that claim already verified works over the wire/comm/static-render
paths; no new mechanism is introduced, only a schema to stop each call site from
re-deriving trait defaults from the vendored source by hand.
