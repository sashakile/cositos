"""Tests for :mod:`cositos.contrib.controls` — the real-controls catalog builder.

Per the design note (`.wai/projects/cositos-core/designs/
2026-07-09-design-controls-catalog-schema-and-scope.md`), each builder function returns
a ``list[ModelEntry]`` whose first entry is the widget itself and whose remaining entries
are its freshly id'd companion models (``LayoutModel``, ``SliderStyleModel``,
``DescriptionStyleModel``). No ``ipywidgets``/``anywidget`` Python package is imported by
this module (verified by ``test_module_imports_no_optional_widget_packages`` here, and
manually in a fresh venv with neither installed — see the module docstring).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from cositos.contrib.controls import dropdown, hbox, int_slider, vbox
from cositos.embed import STATE_MIMETYPE, VIEW_MIMETYPE, embed_html
from cositos.serialize import check_references, dump_document, load_document

_CONTROLS_PY = (
    Path(__file__).resolve().parent.parent / "src" / "cositos" / "contrib" / "controls.py"
)


def _by_id(entries):
    return dict(entries)


def test_int_slider_carries_the_real_controls_identity():
    entries = int_slider()
    root_id, state = entries[0]
    assert state["_model_name"] == "IntSliderModel"
    assert state["_model_module"] == "@jupyter-widgets/controls"
    assert state["_model_module_version"] == "2.0.0"
    assert state["_view_name"] == "IntSliderView"
    assert state["_view_module"] == "@jupyter-widgets/controls"
    assert state["_view_module_version"] == "2.0.0"


def test_int_slider_applies_overrides_over_the_catalog_defaults():
    entries = int_slider(value=7, min=1, max=10)
    _, state = entries[0]
    assert state["value"] == 7
    assert state["min"] == 1
    assert state["max"] == 10
    # Untouched defaults still present.
    assert state["step"] == 1
    assert state["continuous_update"] is True


def test_int_slider_references_freshly_minted_companion_models():
    entries = int_slider()
    root_id, state = entries[0]
    by_id = _by_id(entries)

    style_ref = state["style"]
    layout_ref = state["layout"]
    assert style_ref.startswith("IPY_MODEL_")
    assert layout_ref.startswith("IPY_MODEL_")

    style_id = style_ref.removeprefix("IPY_MODEL_")
    layout_id = layout_ref.removeprefix("IPY_MODEL_")
    assert style_id in by_id
    assert layout_id in by_id
    assert by_id[style_id]["_model_name"] == "SliderStyleModel"
    assert by_id[style_id]["_view_name"] is None
    assert by_id[layout_id]["_model_name"] == "LayoutModel"
    assert by_id[layout_id]["_model_module"] == "@jupyter-widgets/base"


def test_two_int_slider_calls_never_share_a_companion_model_id():
    # The id-uniqueness rule (design note, must-fix #2): every call mints fresh
    # companion ids. Two sliders built back to back must not collide on model_id
    # (dump_document rejects duplicates) nor silently share one companion's state.
    a = int_slider(value=1)
    b = int_slider(value=2)

    a_ids = {mid for mid, _ in a}
    b_ids = {mid for mid, _ in b}
    assert a_ids.isdisjoint(b_ids)

    # Building a document from both must not raise on duplicate model_id.
    doc = dump_document(a + b)
    assert len(doc["state"]) == len(a) + len(b)


def test_dropdown_carries_options_and_the_description_style_companion():
    entries = dropdown(options=["a", "b", "c"], value="b")
    _, state = entries[0]
    by_id = _by_id(entries)

    assert state["_model_name"] == "DropdownModel"
    # Dropdown's options/value/label traits carry no sync=True tag in ipywidgets — only
    # _options_labels/index are wire fields (found via the real-browser check, AC #2).
    assert state["_options_labels"] == ["a", "b", "c"]
    assert state["index"] == 1

    style_id = state["style"].removeprefix("IPY_MODEL_")
    assert by_id[style_id]["_model_name"] == "DescriptionStyleModel"


def test_dropdown_with_no_matching_value_leaves_index_unselected():
    entries = dropdown(options=["a", "b"], value="not-there")
    _, state = entries[0]
    assert state["index"] is None


def test_dropdown_index_override_bypasses_the_value_lookup():
    entries = dropdown(options=["a", "b", "c"], index=2)
    _, state = entries[0]
    assert state["index"] == 2


def test_vbox_composes_children_by_reference():
    slider_entries = int_slider(value=5)
    dropdown_entries = dropdown(options=[1, 2], value=1)

    entries = vbox(children=[slider_entries, dropdown_entries])
    root_id, state = entries[0]

    assert state["_model_name"] == "VBoxModel"
    slider_root_id = slider_entries[0][0]
    dropdown_root_id = dropdown_entries[0][0]
    assert state["children"] == [
        f"IPY_MODEL_{slider_root_id}",
        f"IPY_MODEL_{dropdown_root_id}",
    ]

    # The VBox's own entries list carries all descendants, flattened.
    by_id = _by_id(entries)
    assert slider_root_id in by_id
    assert dropdown_root_id in by_id


def test_hbox_composes_children_by_reference():
    a = int_slider(value=1)
    b = int_slider(value=2)
    entries = hbox(children=[a, b])
    _, state = entries[0]
    assert state["_model_name"] == "HBoxModel"
    assert len(state["children"]) == 2


def test_builder_output_round_trips_losslessly_through_dump_and_load_document():
    entries = vbox(children=[int_slider(value=3), dropdown(options=["x", "y"], value="x")])
    doc = dump_document(entries)

    # No dangling IPY_MODEL_ references (a build-time integrity check the serializer
    # already offers — this proves the builder never emits an orphaned reference).
    check_references(doc)

    reloaded = load_document(doc)
    assert {mid for mid, _ in reloaded} == {mid for mid, _ in entries}
    redumped = dump_document(reloaded)
    assert redumped == doc


def test_module_imports_no_optional_widget_packages():
    # Design intent (research finding #3): the catalog builder needs neither the
    # `ipywidgets` nor the `anywidget` Python package — only the JSON catalog + stdlib.
    # Statically checking the import statements catches a regression without needing a
    # separate venv on every test run (a fresh venv without either package installed was
    # exercised manually once — see the module docstring for that result).
    tree = ast.parse(_CONTROLS_PY.read_text())
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert "ipywidgets" not in imported_roots
    assert "anywidget" not in imported_roots


def test_unknown_catalog_key_is_not_reachable_via_the_public_builders():
    # Guards the trimmed scope (design note): only int_slider/dropdown/vbox/hbox are
    # exposed. Nothing in this pass is expected to reach into the catalog by name.
    import cositos.contrib.controls as controls_mod

    assert not hasattr(controls_mod, "build")


@pytest.mark.parametrize("builder", [int_slider, dropdown])
def test_repeated_calls_mint_distinct_widget_ids_even_with_identical_overrides(builder):
    kwargs = {"value": 1} if builder is int_slider else {"options": [1], "value": 1}
    first = builder(**kwargs)
    second = builder(**kwargs)
    assert first[0][0] != second[0][0]


def test_builder_output_renders_via_embed_html_with_real_view_identity():
    # Static-render check (AC #2): the exported document must carry each real-controls
    # model's OWN view identity untouched — embed_html's with_view_identity() injects
    # anywidget's AnyView identity only where state doesn't already declare one
    # (host-set state wins), so a real controls widget keeps its own view class and the
    # CDN html-manager renders it, not a broken anywidget fallback (cositos-mx7 lineage).
    entries = vbox(children=[int_slider(value=5)])
    doc = dump_document(entries)
    html = embed_html(doc, views=[entries[0][0]])

    assert STATE_MIMETYPE in html
    assert VIEW_MIMETYPE in html
    assert "<!DOCTYPE html>" in html

    state_block = json.loads(
        re.search(
            r'<script type="' + re.escape(STATE_MIMETYPE) + r'">\s*(\{.*?\})\s*</script>',
            html,
            re.DOTALL,
        ).group(1)
    )
    vbox_id = entries[0][0]
    vbox_state = state_block["state"][vbox_id]["state"]
    assert vbox_state["_view_name"] == "VBoxView"
    assert vbox_state["_view_module"] == "@jupyter-widgets/controls"

    slider_id = vbox_state["children"][0].removeprefix("IPY_MODEL_")
    slider_state = state_block["state"][slider_id]["state"]
    assert slider_state["_view_name"] == "IntSliderView"
    assert slider_state["value"] == 5
