"""Compose anywidget widgets in a static export via a real @jupyter-widgets container.

Why this exists (cositos-v38 / cositos-ryh): a plain cositos widget is emitted as
anywidget's ``AnyModel``. ``AnyModel`` declares no *widget-reference* traits, so an
``"IPY_MODEL_<id>"`` string placed in its state (e.g. ``children``) is delivered to the
frontend as a **literal string, not a resolved child model**. Reference-based
composition therefore does NOT work against plain anywidget widgets.

Composition DOES work if the container is a real ipywidgets **controls** model, because
those declare their reference traits with ``widget_serialization`` (the ``unpack_models``
deserializer). This example builds a ``VBoxModel`` (``@jupyter-widgets/controls``) with a
companion ``LayoutModel`` (``@jupyter-widgets/base``) — both at module version ``2.0.0``,
NOT anywidget's ``~0.11.*`` — whose ``children`` resolve to two anywidget children.

Backend-less limitation: ``jslink``/``LinkModel`` does NOT propagate in a static export.
A viewless, unreferenced ``LinkModel`` is never instantiated by the embed html-manager, so
linking widgets requires a live kernel.

Run:  uv run python examples/composition/build.py
Then open examples/composition/vbox.html in any browser (needs internet for the CDN).
"""

from __future__ import annotations

from pathlib import Path

from cositos.embed import embed_html
from cositos.serialize import Document, ModelEntry, dump_document

CHILD_ESM = (
    "export default { render({ model, el }) { el.textContent = 'child: ' + model.get('label'); } }"
)

#: The controls/base container models render with their own view classes, at the
#: ipywidgets module version (2.0.0) — anywidget's ~0.11.* default is wrong for them.
_CONTROLS = "@jupyter-widgets/controls"
_BASE = "@jupyter-widgets/base"
_IPYWIDGETS_VERSION = "2.0.0"


def build_entries() -> list[ModelEntry]:
    """A VBox container (controls) laying out two anywidget children by reference."""
    return [
        (
            "vbox",
            {
                # A real controls container: its ``children`` trait uses widget_serialization,
                # so the IPY_MODEL refs below resolve to the child models on the frontend.
                "_model_name": "VBoxModel",
                "_model_module": _CONTROLS,
                "_model_module_version": _IPYWIDGETS_VERSION,
                "_view_name": "VBoxView",
                "_view_module": _CONTROLS,
                "_view_module_version": _IPYWIDGETS_VERSION,
                "children": ["IPY_MODEL_child_a", "IPY_MODEL_child_b"],
                "layout": "IPY_MODEL_layout",
            },
        ),
        (
            "layout",
            {
                # Companion LayoutModel every controls widget references; it has no view.
                "_model_name": "LayoutModel",
                "_model_module": _BASE,
                "_model_module_version": _IPYWIDGETS_VERSION,
                "_view_name": None,
                "_view_module": _BASE,
                "_view_module_version": _IPYWIDGETS_VERSION,
            },
        ),
        ("child_a", {"_esm": CHILD_ESM, "label": "one"}),
        ("child_b", {"_esm": CHILD_ESM, "label": "two"}),
    ]


def build_document() -> Document:
    """The serialized widget-state Document for the composed UI."""
    return dump_document(build_entries())


def build_html() -> str:
    """A self-contained page that renders only the VBox (its children render inside it)."""
    return embed_html(build_document(), views=["vbox"], title="cositos — composition (VBox)")


if __name__ == "__main__":
    out = Path(__file__).parent / "vbox.html"
    out.write_text(build_html())
    print(f"wrote {out} ({out.stat().st_size} bytes)")
