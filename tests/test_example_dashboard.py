"""Tests for `examples/dashboard/build.py` — real controls + MVU wiring (cositos-70b.4).

The acceptance gate this ticket set is a MUST-NOT: no `ipywidgets.link`/`jslink`/
`traitlets.link` and no peer `.observe()` between the slider/dropdown and the summary
view. That's verified two ways here: a static guard on the module source (this file
literally cannot contain those calls), and a behavioural check that a slider/dropdown
change reaches the summary widget ONLY through the shared host Model, never by one
widget's transport receiving a message addressed to another.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

from cositos.serialize import check_references, dump_document, load_document

_BUILD_PATH = Path(__file__).resolve().parent.parent / "examples" / "dashboard" / "build.py"


def _load_build():
    spec = importlib.util.spec_from_file_location("cositos_dashboard_build", _BUILD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class FakeTransport:
    """The same in-memory fake used by tests/test_model.py — no mocks, a real Transport."""

    supports_receive = True

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict, list, dict | None]] = []
        self._cb = None

    def send(self, msg_type, content, buffers=None, metadata=None):
        self.sent.append((msg_type, content, buffers or [], metadata))

    def on_message(self, callback):
        self._cb = callback

    def deliver(self, data, buffers=None):
        self._cb(data, buffers or [])

    def updates(self):
        return [c["state"] for _t, c, _b, _m in self.sent if c.get("method") == "update"]


@pytest.fixture
def dashboard_and_transports():
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    dashboard.wire(slider_t, dropdown_t, summary_t)
    return dashboard, slider_t, dropdown_t, summary_t


def test_module_source_contains_no_link_or_observe_calls():
    # Static, by-construction guard (not by luck): grep the AST for the exact calls the
    # ticket's MUST-NOT gate forbids. A regression that reintroduces jslink/observe fails
    # here even if it happens to demo fine live.
    source = _BUILD_PATH.read_text()
    tree = ast.parse(source)
    forbidden_names = {"link", "jslink", "dlink", "observe"}
    forbidden_attrs = {"link", "jslink", "dlink", "observe"}
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in forbidden_names:
                pytest.fail(f"forbidden call {func.id}() found in {_BUILD_PATH.name}")
            if isinstance(func, ast.Attribute) and func.attr in forbidden_attrs:
                pytest.fail(f"forbidden call .{func.attr}() found in {_BUILD_PATH.name}")
        elif isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    # The dashboard never needs the ipywidgets Python package (cositos.contrib.controls
    # builds real-controls state directly) -- an actual import, not a mention in prose,
    # is what this guards against.
    assert "ipywidgets" not in imported_roots


def test_slider_change_flows_through_the_host_model_only():
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    dashboard.wire(slider_t, dropdown_t, summary_t)

    for t in (slider_t, dropdown_t, summary_t):
        t.sent.clear()  # drop the three comm_opens; only look at what happens next

    slider_t.deliver({"method": "update", "state": {"value": 77}})

    # The host Model changed...
    assert dashboard.model["value"] == 77
    # ...and ONLY the summary widget was pushed an update — not the dropdown (no peer
    # link/observe: nothing was sent back to the slider's own transport either, since
    # send_state() was never called on the slider widget).
    assert dropdown_t.updates() == []
    assert slider_t.updates() == []
    (summary_state,) = summary_t.updates()
    assert summary_state["text"] == "value=77, selection=low"


def test_dropdown_change_flows_through_the_host_model_only():
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    dashboard.wire(slider_t, dropdown_t, summary_t)
    for t in (slider_t, dropdown_t, summary_t):
        t.sent.clear()

    dropdown_t.deliver({"method": "update", "state": {"index": 2}})

    assert dashboard.model["index"] == 2
    assert slider_t.updates() == []
    assert dropdown_t.updates() == []
    (summary_state,) = summary_t.updates()
    assert summary_state["text"] == "value=25, selection=high"


def test_get_state_always_reflects_the_current_host_model():
    # "The summary view re-renders from get_state only" (AC) — after the model changes,
    # a fresh get_state() call (what request_state / a later send_state() would use)
    # must reflect it, without needing to re-observe anything.
    build = _load_build()
    dashboard = build.Dashboard(options=["a", "b"], value=1, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    dashboard.wire(slider_t, dropdown_t, summary_t)

    slider_t.deliver({"method": "update", "state": {"value": 9}})
    assert dashboard._get_slider_state()["value"] == 9
    assert dashboard._get_summary_state()["text"] == "value=9, selection=a"


def test_an_equal_value_update_does_not_re_render():
    build = _load_build()
    dashboard = build.Dashboard(options=["a", "b"], value=5, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    dashboard.wire(slider_t, dropdown_t, summary_t)
    summary_t.sent.clear()

    slider_t.deliver({"method": "update", "state": {"value": 5}})  # no-op change

    assert summary_t.updates() == []


def test_out_of_range_index_renders_a_none_placeholder_not_a_crash():
    build = _load_build()
    dashboard = build.Dashboard(options=["a", "b"], value=0, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    dashboard.wire(slider_t, dropdown_t, summary_t)
    summary_t.sent.clear()

    dropdown_t.deliver({"method": "update", "state": {"index": 99}})

    (summary_state,) = summary_t.updates()
    assert summary_state["text"] == "value=0, selection=(none)"


def test_dashboard_requires_at_least_one_option():
    build = _load_build()
    with pytest.raises(ValueError, match="at least one"):
        build.Dashboard(options=[])


def test_wire_with_companion_transports_opens_every_referenced_companion_model():
    # A companion (LayoutModel/SliderStyleModel/DescriptionStyleModel) is a distinct
    # model that a REAL frontend can only resolve if it separately received a
    # comm_open for it — composing fine in the static export (one flattened Document)
    # doesn't imply that live. wire() must open one comm per companion when asked.
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
    companion_entries = dashboard._slider_entries[1:] + dashboard._dropdown_entries[1:]
    assert len(companion_entries) == 4  # SliderStyle+Layout, DescriptionStyle+Layout

    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    companion_ts = [FakeTransport() for _ in companion_entries]
    dashboard.wire(slider_t, dropdown_t, summary_t, companion_transports=companion_ts)

    assert len(dashboard._companion_widgets) == 4
    for widget, (model_id, _state), transport in zip(
        dashboard._companion_widgets, companion_entries, companion_ts, strict=True
    ):
        assert widget.model_id == model_id
        (opened_type, opened_content, _b, _m) = transport.sent[0]
        assert opened_type == "comm_open"
        assert (
            opened_content["state"]["_model_name"]
            == dict(companion_entries)[model_id]["_model_name"]
        )


def test_wire_rejects_a_mismatched_number_of_companion_transports():
    build = _load_build()
    dashboard = build.Dashboard(options=["a", "b"], value=0, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()

    with pytest.raises(ValueError, match="companion_transports"):
        dashboard.wire(slider_t, dropdown_t, summary_t, companion_transports=[FakeTransport()])


def test_build_entries_round_trips_losslessly_through_dump_and_load_document():
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=1)
    entries = dashboard.build_entries()
    doc = dump_document(entries)

    check_references(doc)  # no dangling IPY_MODEL_ refs
    reloaded = load_document(doc)
    assert {mid for mid, _ in reloaded} == {mid for mid, _ in entries}
    assert dump_document(reloaded) == doc


def test_build_entries_carries_no_link_model_ever_by_construction():
    # Mirrors examples/benchmarks/benchlib.py's links_kept metric (there: counts
    # LinkModel survivors after embed_data; here: == 0 because the dashboard never
    # creates one, not because none happened to survive serialization).
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
    doc = dump_document(dashboard.build_entries())

    links_kept = sum(1 for record in doc["state"].values() if record["model_name"] == "LinkModel")
    assert links_kept == 0


def test_build_entries_composes_slider_dropdown_and_summary_in_one_real_vbox():
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
    entries = dashboard.build_entries()
    vbox_id, vbox_state = entries[0]
    by_id = dict(entries)

    assert vbox_state["_model_name"] == "VBoxModel"
    child_ids = {ref.removeprefix("IPY_MODEL_") for ref in vbox_state["children"]}
    assert dashboard.slider_id in child_ids
    assert dashboard.dropdown_id in child_ids
    assert dashboard.summary_id in child_ids
    assert by_id[dashboard.slider_id]["_model_name"] == "IntSliderModel"
    assert by_id[dashboard.dropdown_id]["_model_name"] == "DropdownModel"
    assert by_id[dashboard.summary_id]["_esm"] == build.SUMMARY_ESM


def test_build_html_and_build_document_use_the_same_default_dashboard():
    build = _load_build()
    doc = build.build_document()
    html = build.build_html()

    assert doc["state"]
    assert "<!DOCTYPE html>" in html
    from cositos.embed import STATE_MIMETYPE, VIEW_MIMETYPE

    assert STATE_MIMETYPE in html
    assert VIEW_MIMETYPE in html


# ---- Download & restore (cositos-70b.5) ----


def test_download_button_is_composed_into_build_entries_with_current_json():
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
    entries = dashboard.build_entries()
    vbox_id, vbox_state = entries[0]
    by_id = dict(entries)

    child_ids = {ref.removeprefix("IPY_MODEL_") for ref in vbox_state["children"]}
    assert dashboard.download_id in child_ids
    download_state = by_id[dashboard.download_id]
    assert download_state["_esm"] == build.DOWNLOAD_BUTTON_ESM
    assert download_state["filename"] == "dashboard-state.json"

    import json

    saved_doc = json.loads(download_state["json"])
    # The download's own JSON does NOT reference itself (no self-referential document).
    assert dashboard.download_id not in saved_doc["state"]
    assert dashboard.slider_id in saved_doc["state"]
    assert saved_doc["state"][dashboard.slider_id]["state"]["value"] == 25


def test_download_json_refreshes_on_every_render_like_the_summary():
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    download_t = FakeTransport()
    dashboard.wire(slider_t, dropdown_t, summary_t, download_transport=download_t)
    download_t.sent.clear()

    slider_t.deliver({"method": "update", "state": {"value": 77}})

    (download_update,) = download_t.updates()
    import json

    saved_doc = json.loads(download_update["json"])
    assert saved_doc["state"][dashboard.slider_id]["state"]["value"] == 77


def test_download_button_never_receives_inbound_state_from_slider_or_dropdown():
    # Same MUST-NOT gate as cositos-70b.4: the download button is a pure projection,
    # never a peer the slider/dropdown talk to directly.
    build = _load_build()
    dashboard = build.Dashboard(options=["a", "b"], value=0, index=0)
    slider_t, dropdown_t, summary_t = FakeTransport(), FakeTransport(), FakeTransport()
    download_t = FakeTransport()
    dashboard.wire(slider_t, dropdown_t, summary_t, download_transport=download_t)

    assert dashboard.download_widget is not None
    assert dashboard.download_widget._set_state is None


def test_restore_document_recovers_the_downloaded_state_in_a_fresh_session(tmp_path):
    # The ticket's full end-to-end scenario: build -> "click download" (grab the JSON
    # the button would have saved) -> write it to a real file -> read it back in a
    # FRESH session (no shared Dashboard instance, no in-memory reuse) -> restore ->
    # assert it equals what was downloaded -> rebuild and get the same on-screen values.
    build = _load_build()
    dashboard = build.Dashboard(options=["low", "medium", "high"], value=42, index=2)
    download_state = dashboard._get_download_state()

    saved_file = tmp_path / "dashboard-state.json"
    saved_file.write_text(download_state["json"])  # simulates the real browser download

    # Fresh session: only the file on disk, no reference to `dashboard` from here on.
    downloaded_json_text = saved_file.read_text()
    restored_doc = build.restore_document(downloaded_json_text)
    restored_entries = load_document(restored_doc)
    by_id = dict(restored_entries)

    # Assert the restored state equals what was downloaded...
    assert dump_document(restored_entries) == restored_doc
    assert by_id[dashboard.slider_id]["value"] == 42
    assert by_id[dashboard.dropdown_id]["index"] == 2
    assert by_id[dashboard.summary_id]["text"] == "value=42, selection=high"

    # ...and re-rendering (embed_html on the restored document) reproduces the same
    # on-screen dashboard: the same real controls identity, the same values.
    from cositos.embed import embed_html

    html = embed_html(restored_doc, views=[dashboard.slider_id, dashboard.dropdown_id])
    assert by_id[dashboard.slider_id]["_model_name"] == "IntSliderModel"
    embedded_state = restored_doc["state"][dashboard.slider_id]["state"]
    assert embedded_state["value"] == 42
    assert html  # renders without raising
