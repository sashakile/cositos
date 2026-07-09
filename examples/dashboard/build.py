"""Dashboard example: a real IntSlider + Dropdown drive a summary view, MVU-style.

Master-detail-lite scenario (`cositos-70b.4`): an `IntSlider` and a `Dropdown` — real
`@jupyter-widgets/controls` models from `cositos.contrib.controls`, not reimplemented —
drive a small custom anywidget summary view. All three widgets are pure projections of
**one** host-side Model (`Dashboard.model`); nothing observes anything else.

## Why this matters (the acceptance gate this file exists to satisfy)

`ipywidgets.link`/`jslink`/`traitlets.link`, or a peer `.observe()` between the slider,
dropdown, and summary widgets, would be the "idiomatic" one-liner here — and would demo
fine, live, in a running kernel. It would then silently produce a summary view with
stale or wrong content the moment the dashboard's state is downloaded and restored
(`cositos-70b.5`), because a `LinkModel` does not survive a backend-less static export
(`docs/tutorials/static-export.qmd`, "`jslink` does not work in static export") and a
peer `.observe()` callback is host-side Python state that a state *file* never captures
at all. Neither failure raises an error; the widget just stops updating.

This module therefore contains **no** `ipywidgets.link`/`jslink`/`traitlets.link` and
**no** widget-to-widget `.observe()` — by construction, not by convention. Every inbound
change from the slider or dropdown flows through `Dashboard._set_slider_state`/
`_set_dropdown_state` into the single `self.model` dict; `Dashboard._render` is the only
place that recomputes the summary text and pushes it out. This mirrors
`examples/benchmarks/masterdetail.py`'s MVU variant B (`dispatch`/`render` split) and is
grounded in `claim:01KWX49WFJ1F31348M12R2S93E` (peer link/observe explodes cost and never
serializes — `links_kept=0` in every benchmark scenario that avoids it).

Run: ``uv run python examples/dashboard/build.py`` writes `dashboard.html` (a static
snapshot — see `docs/tutorials/static-export.qmd` for what static export can and cannot
show: the widgets render, but only a live kernel can dispatch new slider/dropdown values).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cositos.contrib.controls import dropdown, int_slider, vbox
from cositos.embed import embed_html
from cositos.model import Widget
from cositos.serialize import Document, ModelEntry, dump_document
from cositos.transport import Transport

#: The summary view is a plain, minimal anywidget — cositos' own "build a widget" path
#: (see `docs/widgets.md`), deliberately NOT another real-controls model: the point of
#: this example is that a real control and a hand-written one compose through the same
#: host Model with no special-casing.
SUMMARY_ESM = """
export default {
  render({ model, el }) {
    const paint = () => { el.textContent = model.get("text"); };
    paint();
    model.on("change:text", paint);
  },
};
"""


class Dashboard:
    """The single MVU host Model driving the slider, dropdown, and summary widgets.

    Each widget's `get_state`/`set_state` pair reads and writes **only its own slice**
    of `self.model` — never another widget's state, and never by observing another
    widget. `_render()` is the sole place the summary text is computed and pushed.
    """

    def __init__(self, options: list[str], value: int = 0, index: int = 0) -> None:
        if not options:
            raise ValueError("Dashboard requires at least one dropdown option")
        self.options = list(options)
        #: The ONE host Model. Every widget is a pure projection of this dict; every
        #: inbound change is applied here before anything re-renders.
        self.model: dict[str, Any] = {"value": value, "index": index}

        self._slider_entries = int_slider(value=value, min=0, max=100)
        self._dropdown_entries = dropdown(options=self.options, index=index)
        self.slider_id, self._slider_state = self._slider_entries[0]
        self.dropdown_id, self._dropdown_state = self._dropdown_entries[0]
        self.summary_id = f"{self.slider_id}-summary"

        self.slider_widget: Widget | None = None
        self.dropdown_widget: Widget | None = None
        self.summary_widget: Widget | None = None
        #: Static companion models (`LayoutModel`, `SliderStyleModel`,
        #: `DescriptionStyleModel`) referenced by the slider/dropdown's `IPY_MODEL_<id>`
        #: fields. A live kernel comm only carries ONE model's state; the frontend
        #: resolves a reference by looking up a model it has separately received a
        #: `comm_open` for. Composition working in the static export (`build_entries`
        #: flattens every descendant into one Document) does NOT imply it works live
        #: unless every referenced companion also gets its own opened comm — `wire()`
        #: below does that; skipping it would silently break the layout/style trait
        #: resolution the moment this dashboard is opened against a real JupyterLab
        #: kernel instead of the fake/subprocess-only checks in this repo's test suite.
        self._companion_widgets: list[Widget] = []

    # ---- the summary projection: the ONLY function that computes its text ----

    def _summary_text(self) -> str:
        idx = self.model["index"]
        in_range = idx is not None and 0 <= idx < len(self.options)
        label = self.options[idx] if in_range else "(none)"
        return f"value={self.model['value']}, selection={label}"

    def _render(self) -> None:
        """Push the recomputed summary. The only place any widget is told to update."""
        if self.summary_widget is not None:
            self.summary_widget.send_state()

    # ---- slider: reads/writes ONLY self.model["value"] ----

    def _get_slider_state(self) -> dict[str, Any]:
        return {**self._slider_state, "value": self.model["value"]}

    def _set_slider_state(self, state: dict[str, Any]) -> None:
        if "value" not in state or state["value"] == self.model["value"]:
            return
        self.model["value"] = state["value"]
        self._render()

    # ---- dropdown: reads/writes ONLY self.model["index"] ----

    def _get_dropdown_state(self) -> dict[str, Any]:
        return {**self._dropdown_state, "index": self.model["index"]}

    def _set_dropdown_state(self, state: dict[str, Any]) -> None:
        if "index" not in state or state["index"] == self.model["index"]:
            return
        self.model["index"] = state["index"]
        self._render()

    # ---- summary: read-only projection, never accepts inbound state ----

    def _get_summary_state(self) -> dict[str, Any]:
        return {"_esm": SUMMARY_ESM, "text": self._summary_text()}

    def wire(
        self,
        slider_transport: Transport,
        dropdown_transport: Transport,
        summary_transport: Transport,
        companion_transports: list[Transport] | None = None,
    ) -> None:
        """Open all three interactive widgets, and every static companion model.

        ``companion_transports`` must supply one transport per companion in
        `self._slider_entries[1:] + self._dropdown_entries[1:]` (in that order) — each
        companion is a distinct model and needs its own comm to be resolvable by a real
        frontend. Omit it only for tests that don't care about companion resolution
        (e.g. a fake-transport unit test asserting the slider/dropdown/summary dispatch
        seam in isolation).
        """
        self.slider_widget = Widget(
            slider_transport,
            get_state=self._get_slider_state,
            set_state=self._set_slider_state,
            model_id=self.slider_id,
        )
        self.dropdown_widget = Widget(
            dropdown_transport,
            get_state=self._get_dropdown_state,
            set_state=self._set_dropdown_state,
            model_id=self.dropdown_id,
        )
        self.summary_widget = Widget(
            summary_transport,
            get_state=self._get_summary_state,
            model_id=self.summary_id,
        )
        self.slider_widget.open()
        self.dropdown_widget.open()
        self.summary_widget.open()

        companion_entries = self._slider_entries[1:] + self._dropdown_entries[1:]
        if companion_transports is not None:
            if len(companion_transports) != len(companion_entries):
                raise ValueError(
                    f"wire() needs {len(companion_entries)} companion_transports, "
                    f"got {len(companion_transports)}"
                )
            self._companion_widgets = [
                Widget(transport, get_state=(lambda s=state: dict(s)), model_id=model_id)
                for (model_id, state), transport in zip(
                    companion_entries, companion_transports, strict=True
                )
            ]
            for widget in self._companion_widgets:
                widget.open()

    def build_entries(self) -> list[ModelEntry]:
        """A static snapshot: slider + dropdown + summary composed in one real VBox.

        Uses the SAME companion-model ids minted in `__init__` (not fresh ones), so a
        static export and a live-wired dashboard describe the identical widget tree.
        """
        summary_entry: ModelEntry = (self.summary_id, self._get_summary_state())
        return vbox(children=[self._slider_entries, self._dropdown_entries, [summary_entry]])


def build_document(dashboard: Dashboard | None = None) -> Document:
    """The serialized widget-state Document for a default (or given) dashboard."""
    dashboard = dashboard or Dashboard(options=["low", "medium", "high"], value=25, index=0)
    return dump_document(dashboard.build_entries())


def build_html(dashboard: Dashboard | None = None) -> str:
    """A self-contained static page rendering the dashboard's top-level VBox."""
    dashboard = dashboard or Dashboard(options=["low", "medium", "high"], value=25, index=0)
    entries = dashboard.build_entries()
    doc = dump_document(entries)
    root_id = entries[0][0]
    return embed_html(doc, views=[root_id], title="cositos — dashboard (real controls + MVU)")


if __name__ == "__main__":
    out = Path(__file__).parent / "dashboard.html"
    out.write_text(build_html())
    print(f"wrote {out} ({out.stat().st_size} bytes)")
