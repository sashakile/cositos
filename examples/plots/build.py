"""Harvest an existing plotting widget into a cositos static export.

The point: you do **not** rebuild a plot as a cositos widget. Any widget already built with
ipywidgets — including anywidget-based plotting libraries — is captured verbatim by
:func:`cositos.contrib.harvest`, because ``ipywidgets.embed.embed_data`` already returns a
cositos v2 Widget-State :data:`~cositos.serialize.Document`. Here we take a live Plotly
``FigureWidget`` and write a self-contained HTML page that renders with no kernel.

Why Plotly works with zero special-casing: Plotly 6's ``FigureWidget`` is **anywidget-based**
(``_model_module == "anywidget"``), which is exactly the frontend cositos targets, so the
CDN html-manager resolves its view the same way it resolves a native cositos widget. Altair's
``JupyterChart`` is anywidget-based too and behaves identically.

bqplot caveat (see the module note at the bottom): bqplot is **not** anywidget-based — it
ships its own ``bqplot`` / ``bqscales`` frontend modules. ``harvest`` still produces a valid
Document, but static rendering then depends on the html-manager being able to load those
custom modules from the CDN; it is not the guaranteed-resolvable anywidget path.

Run:  uv run --with plotly python examples/plots/build.py
Then open examples/plots/plotly.html in any browser (needs internet for the CDN).
"""

from __future__ import annotations

from pathlib import Path


def build_html() -> str:
    """Build a Plotly FigureWidget and render it to static HTML through cositos."""
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover - example guard, not a unit under test
        raise SystemExit(
            "this example needs plotly: `uv run --with plotly python examples/plots/build.py`"
        ) from exc

    from cositos.contrib import harvest_html

    fig = go.FigureWidget(
        data=[go.Bar(x=["Mon", "Tue", "Wed", "Thu", "Fri"], y=[4, 7, 3, 8, 5])],
        layout={"title": {"text": "Harvested through cositos"}},
    )
    # harvest_html renders only the FigureWidget as a view (its auxiliary layout/style
    # models are embedded as state but are not turned into viewless view scripts).
    return harvest_html(fig, title="cositos — harvested Plotly FigureWidget")


if __name__ == "__main__":
    out = Path(__file__).parent / "plotly.html"
    out.write_text(build_html())
    print(f"wrote {out} ({out.stat().st_size} bytes)")
