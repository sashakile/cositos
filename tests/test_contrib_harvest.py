"""Tests for :mod:`cositos.contrib.harvest` — wrapping an existing ipywidgets tree.

``harvest`` delegates to ``ipywidgets.embed.embed_data`` and returns a cositos
:data:`~cositos.serialize.Document`, so an app built with stock ipywidgets (or any
ipywidgets-based library) can be serialized and statically embedded through cositos with
no core changes. Skipped automatically when ipywidgets is not installed
(``pip install .[oracle]``).
"""

import pytest

ipywidgets = pytest.importorskip("ipywidgets")

from cositos.contrib import harvest, harvest_html  # noqa: E402
from cositos.embed import STATE_MIMETYPE, VIEW_MIMETYPE, embed_html  # noqa: E402
from cositos.serialize import (  # noqa: E402
    STATE_VERSION_MAJOR,
    STATE_VERSION_MINOR,
    dump_document,
    load_document,
)


def test_harvest_returns_a_v2_document():
    doc = harvest(ipywidgets.IntSlider(value=7))

    assert doc["version_major"] == STATE_VERSION_MAJOR
    assert doc["version_minor"] == STATE_VERSION_MINOR
    assert isinstance(doc["state"], dict)
    assert doc["state"], "a harvested widget must contribute at least one model"


def test_harvest_document_round_trips_through_the_codec():
    slider = ipywidgets.IntSlider(value=42)
    doc = harvest(slider)

    # load_document -> dump_document is the identity on a well-formed Document.
    reserialized = dump_document(load_document(doc))

    assert reserialized["state"].keys() == doc["state"].keys()
    assert slider.model_id in reserialized["state"]


def test_harvest_captures_a_composed_tree_by_reference():
    child = ipywidgets.IntSlider(value=1)
    box = ipywidgets.VBox([child])
    doc = harvest(box)

    # Both the container and its child are present, and the child is held by reference.
    assert box.model_id in doc["state"]
    assert child.model_id in doc["state"]
    box_state = doc["state"][box.model_id]["state"]
    assert f"IPY_MODEL_{child.model_id}" in box_state["children"]


def test_harvest_of_multiple_widgets_yields_one_document():
    a = ipywidgets.IntSlider()
    b = ipywidgets.Text()
    doc = harvest(a, b)

    assert a.model_id in doc["state"]
    assert b.model_id in doc["state"]


def test_harvest_document_embeds_as_static_html():
    doc = harvest(ipywidgets.IntSlider(value=7))
    html = embed_html(doc)

    assert STATE_MIMETYPE in html
    assert "<!DOCTYPE html>" in html


def test_harvest_html_renders_only_top_level_widgets_as_views():
    # A slider expands to slider + layout + style models, but only the slider is a view.
    slider = ipywidgets.IntSlider(value=7)
    html = harvest_html(slider)

    assert STATE_MIMETYPE in html
    # Exactly one widget-view+json script — the top-level slider, not its layout/style.
    assert html.count(VIEW_MIMETYPE) == 1
    assert slider.model_id in html


def test_harvest_requires_at_least_one_widget():
    with pytest.raises(ValueError, match="at least one widget"):
        harvest()


anywidget = pytest.importorskip("anywidget")
traitlets = pytest.importorskip("traitlets")


class _ConstEsmWidget(anywidget.AnyWidget):
    """An anywidget subclass that declares ``_esm`` as a *class-level* default — the
    common pattern for widgets that bundle their own frontend (e.g. Plotly's
    ``FigureWidget``, which bakes its ~5MB bundled JS module in as the trait's default
    value rather than setting it per instance).
    """

    _esm = "export default { render({ model, el }) { el.innerText = model.get('value'); } }"
    value = traitlets.Int(0).tag(sync=True)


def test_harvest_preserves_esm_declared_as_a_class_level_trait_default():
    # Regression (cositos-b2t): ipywidgets.embed.embed_data defaults to
    # drop_defaults=True, which compares each trait's *current* value against its
    # *class-level default* and omits it if they match. A widget that bundles its
    # frontend by setting `_esm` as the trait's default (not a per-instance override,
    # as real anywidget-based Plotly FigureWidget/Altair JupyterChart do) therefore has
    # `_esm` silently dropped from the harvested state. The CDN anywidget runtime's
    # AnyView then calls `isHref(undefined)` and throws
    # "Cannot read properties of undefined (reading 'startsWith')" instead of rendering.
    widget = _ConstEsmWidget()
    doc = harvest(widget)
    state = doc["state"][widget.model_id]["state"]
    assert "_esm" in state
    assert state["_esm"] == _ConstEsmWidget._esm


def test_harvest_html_embeds_esm_declared_as_a_class_level_trait_default():
    widget = _ConstEsmWidget()
    html = harvest_html(widget)
    assert "_esm" in html
