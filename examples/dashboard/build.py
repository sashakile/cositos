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

## Download & restore (cositos-70b.5)

The dashboard also carries a `download_button.js` widget (`examples/widgets/`) whose
`json` state field is always the CURRENT `dump_document(...)` of the slider/dropdown/
summary tree — computed the same MVU way as the summary text: `Dashboard._render` pushes
it on every model change, never by the download button observing anything itself.
Clicking it triggers a real browser download of that JSON
(`docs/tutorials/save-restore.qmd#download-restore-a-dashboards-state` covers the restore
side: `load_document` the downloaded file in a fresh session and rebuild).
"""

from __future__ import annotations

import json as json_module
from pathlib import Path
from typing import Any

from cositos.contrib.controls import dropdown, int_slider, vbox
from cositos.embed import embed_html
from cositos.model import Widget
from cositos.serialize import Document, ModelEntry, dump_document
from cositos.transport import Transport

#: The unmodified download-state widget ESM (cositos-70b.5) — read from the shared
#: examples/widgets/ directory rather than duplicated inline, so the Python glue here and
#: the JS gallery test (front/test/gallery.test.js) exercise the exact same file.
DOWNLOAD_BUTTON_ESM = (
    Path(__file__).resolve().parent.parent / "widgets" / "download_button.js"
).read_text()

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
        self.download_id = f"{self.slider_id}-download"
        self.download_widget: Widget | None = None
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
        """Push the recomputed summary + the refreshed download JSON.

        The ONLY place any widget is told to update — the download button's `json` is
        recomputed here exactly like the summary text, via `self.model`, never by
        observing the slider/dropdown itself (the same MUST-NOT gate `cositos-70b.4`
        set applies here: a stale download button is the whole reason that gate exists).
        """
        if self.summary_widget is not None:
            self.summary_widget.send_state()
        if self.download_widget is not None:
            self.download_widget.send_state()

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

    # ---- download button: read-only projection of the OTHER three widgets' Document ----

    def _dashboard_document_json(self) -> str:
        """The current slider/dropdown/summary state, serialized — what Download saves.

        Deliberately excludes the download button's OWN entry (there would be nothing
        useful to restore from a document that references itself before it exists).
        Reads the slider/dropdown state through `_get_slider_state`/`_get_dropdown_state`
        (through `self.model`), not the static `_slider_entries[0]`/`_dropdown_entries[0]`
        captured at construction time — otherwise a downloaded file would always save the
        dashboard's INITIAL values, never whatever the user actually set (the exact
        staleness bug the MUST-NOT gate on cositos-70b.4 exists to prevent, just in the
        Python glue instead of a widget link).
        """
        slider_entry: ModelEntry = (self.slider_id, self._get_slider_state())
        dropdown_entry: ModelEntry = (self.dropdown_id, self._get_dropdown_state())
        summary_entry: ModelEntry = (self.summary_id, self._get_summary_state())
        companion_entries = self._slider_entries[1:] + self._dropdown_entries[1:]
        entries = [slider_entry, dropdown_entry, summary_entry, *companion_entries]
        return json_module.dumps(dump_document(entries))

    def _get_download_state(self) -> dict[str, Any]:
        return {
            "_esm": DOWNLOAD_BUTTON_ESM,
            "json": self._dashboard_document_json(),
            "filename": "dashboard-state.json",
            "label": "Download dashboard state",
        }

    def wire(
        self,
        slider_transport: Transport,
        dropdown_transport: Transport,
        summary_transport: Transport,
        companion_transports: list[Transport] | None = None,
        download_transport: Transport | None = None,
    ) -> None:
        """Open all interactive/read-only widgets, and every static companion model.

        ``companion_transports`` must supply one transport per companion in
        `self._slider_entries[1:] + self._dropdown_entries[1:]` (in that order) — each
        companion is a distinct model and needs its own comm to be resolvable by a real
        frontend. Omit it only for tests that don't care about companion resolution
        (e.g. a fake-transport unit test asserting the slider/dropdown/summary dispatch
        seam in isolation). ``download_transport`` opens the download-state button;
        omit it if a test doesn't care about the download path either.
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

        if download_transport is not None:
            self.download_widget = Widget(
                download_transport,
                get_state=self._get_download_state,
                model_id=self.download_id,
            )
            self.download_widget.open()

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
        """A static snapshot: slider + dropdown + summary + download composed in one VBox.

        Uses the SAME companion-model ids minted in `__init__` (not fresh ones), so a
        static export and a live-wired dashboard describe the identical widget tree.
        """
        summary_entry: ModelEntry = (self.summary_id, self._get_summary_state())
        download_entry: ModelEntry = (self.download_id, self._get_download_state())
        return vbox(
            children=[
                self._slider_entries,
                self._dropdown_entries,
                [summary_entry],
                [download_entry],
            ]
        )


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


def restore_document(json_text: str) -> Document:
    """The other half of Download & restore (cositos-70b.5): parse a downloaded file.

    ``json_text`` is exactly what `download_button.js`'s `json` state field held (and
    what a real browser click saves to disk) — the plain-JSON encoding of a cositos
    :data:`~cositos.serialize.Document`. This is a thin, obvious wrapper (`json.loads`)
    that exists so the restore-from-file recipe in `docs/tutorials/save-restore.qmd` has
    one call to point at, matching the ticket's "docs-only restore path, no new upload
    widget" scope: there is nothing here to wire up live, just `load_document` on
    whatever bytes the host's upload mechanism (a Jupyter file-upload cell,
    `open(path).read()`, …) produced.
    """
    return json_module.loads(json_text)


if __name__ == "__main__":
    out = Path(__file__).parent / "dashboard.html"
    out.write_text(build_html())
    print(f"wrote {out} ({out.stat().st_size} bytes)")
