"""Build a static HTML page from a notebook containing a cositos widget — no kernel.

This is the mechanism every nbconvert-based static builder (JupyterBook) and Quarto share:

1. A widget cell's *output* is a `widget-view+json` mimebundle (what
   `Widget._repr_mimebundle_` emits when the widget is displayed).
2. The *notebook* metadata carries the widget-state `Document` under
   `metadata.widgets["application/vnd.jupyter.widget-state+json"]`.

Because cositos widgets do not register with an ipywidgets manager, step 2 must be done
explicitly (the manager normally writes it on save). `inject_widget_state` does that.

Run:  uv run --with nbconvert --with nbformat python examples/static-export/build.py
Then open examples/static-export/counter.html in any browser (needs internet for the CDN).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cositos.embed import STATE_MIMETYPE, VIEW_MIMETYPE, with_view_identity
from cositos.serialize import Document, ModelEntry, dump_document

COUNTER_ESM = (
    "export default { render({ model, el }) { el.textContent = 'count = ' + model.get('n'); } }"
)


def build_notebook(entries: list[ModelEntry], view_ids: list[str]) -> Any:
    """A notebook with one displayed-widget cell per view and the state in metadata."""
    from nbformat.v4 import new_code_cell, new_notebook, new_output  # noqa: PLC0415

    cells = []
    for mid in view_ids:
        cell = new_code_cell("widget")
        cell.outputs = [
            new_output(
                "display_data",
                data={
                    VIEW_MIMETYPE: {
                        "version_major": 2,
                        "version_minor": 0,
                        "model_id": mid,
                    },
                    "text/plain": f"cositos widget {mid!r}",
                },
                metadata={},
            )
        ]
        cells.append(cell)
    nb = new_notebook(cells=cells)
    inject_widget_state(nb, dump_document(entries))
    return nb


def inject_widget_state(nb: Any, document: Document) -> None:
    """Put the widget-state Document where nbconvert/Quarto/JupyterBook read it.

    The document is enriched with anywidget view identity so the CDN html-manager can
    render it (cositos-mx7); without it the export is structurally valid but unrenderable.
    """
    nb.metadata["widgets"] = {STATE_MIMETYPE: with_view_identity(document)}


def build_html(entries: list[ModelEntry], view_ids: list[str]) -> str:
    from nbconvert import HTMLExporter  # noqa: PLC0415

    html, _ = HTMLExporter().from_notebook_node(build_notebook(entries, view_ids))
    return html


if __name__ == "__main__":
    entries: list[ModelEntry] = [("counter", {"_esm": COUNTER_ESM, "n": 3})]
    out = Path(__file__).parent / "counter.html"
    out.write_text(build_html(entries, ["counter"]))
    print(f"wrote {out} ({out.stat().st_size} bytes)")
