"""Oracle test: cositos protocol output must match real anywidget's comm traffic.

Uses an installed anywidget as the source of truth. anywidget is ipywidgets-based, so it
sends extra DOMWidget fields (layout, tabbable, …) that cositos (a thin, Deno-profile
core) intentionally omits. We therefore assert cositos reproduces the *overlapping*
protocol surface: target, metadata/version, immutable model/view identity, and the
`update` message shape.

Skipped automatically when anywidget/comm are not installed (``pip install .[oracle]``).
"""

import pytest

anywidget = pytest.importorskip("anywidget")
comm_pkg = pytest.importorskip("comm")
traitlets = pytest.importorskip("traitlets")

from cositos import build_comm_open, build_update  # noqa: E402
from cositos.protocol import ANYWIDGET_MODULE_VERSION  # noqa: E402


class _RecordingComm:
    def __init__(self, **kw):
        self.comm_id = "oracle-comm"
        self.kernel = True
        self.open_kwargs = kw
        self.sends = []

    def send(self, data=None, metadata=None, buffers=None):
        self.sends.append({"data": data, "buffers": buffers, "metadata": metadata})

    def on_msg(self, cb):
        self._on_msg = cb

    def on_close(self, cb):
        pass

    def close(self, *a, **k):
        pass


@pytest.fixture
def anywidget_traffic(monkeypatch):
    """Instantiate a real anywidget widget and capture its comm_open + one update."""
    recorded = {}

    def _factory(**kw):
        c = _RecordingComm(**kw)
        recorded["comm"] = c
        return c

    monkeypatch.setattr(comm_pkg, "create_comm", _factory)

    class Counter(anywidget.AnyWidget):
        _esm = "export default { render({model, el}) { el.innerText = model.get('value'); } }"
        value = traitlets.Int(0).tag(sync=True)

    widget = Counter()
    widget._repr_mimebundle_()
    widget.value = 5  # trigger an update send
    return recorded["comm"]


def test_comm_open_target_and_metadata_match_anywidget(anywidget_traffic):
    ref = anywidget_traffic.open_kwargs
    data, _buffers, metadata = build_comm_open({"_esm": "x", "value": 0})
    assert ref["target_name"] == "jupyter.widget"
    assert metadata == ref["metadata"]  # {"version": "2.1.0"}


def test_immutable_identity_fields_match_anywidget(anywidget_traffic):
    ref_state = anywidget_traffic.open_kwargs["data"]["state"]
    data, _b, _m = build_comm_open({"_esm": "x"})
    state = data["state"]
    for key in ("_model_module", "_model_name", "_view_module", "_view_name", "_view_count"):
        assert state[key] == ref_state[key], key


def test_module_version_tracks_installed_anywidget(anywidget_traffic):
    ref_state = anywidget_traffic.open_kwargs["data"]["state"]
    # cositos's default version range should be compatible with the installed anywidget.
    # Both are semver ranges of the form "~0.MINOR.*"; assert the minor lines up.
    ref = ref_state["_model_module_version"]
    assert ref.split(".")[1] == ANYWIDGET_MODULE_VERSION.split(".")[1], (
        f"cositos targets {ANYWIDGET_MODULE_VERSION} but installed anywidget uses {ref}"
    )


def test_update_message_shape_matches_anywidget(anywidget_traffic):
    ref_update = next(
        s["data"] for s in anywidget_traffic.sends if s["data"].get("method") == "update"
    )
    data, _buffers = build_update({"value": 5})
    assert data == ref_update  # {"method":"update","state":{"value":5},"buffer_paths":[]}
