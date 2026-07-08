"""Unit tests for the Jupyter CommTransport, using a fake `comm` (no live kernel)."""

import pytest

comm_pkg = pytest.importorskip("comm")

from cositos import Widget  # noqa: E402
from cositos.jupyter import CommTransport  # noqa: E402


class FakeComm:
    def __init__(self, target_name, data, metadata, buffers):
        self.comm_id = "fake-comm-123"
        self.target_name = target_name
        self.open_data = data
        self.open_metadata = metadata
        self.open_buffers = buffers
        self.sends = []
        self.closed = False
        self._on_msg = None

    def send(self, data=None, buffers=None):
        self.sends.append({"data": data, "buffers": buffers})

    def on_msg(self, cb):
        self._on_msg = cb

    def close(self):
        self.closed = True

    def receive(self, data, buffers=None):
        """Simulate an inbound frontend message."""
        self._on_msg({"content": {"data": data}, "buffers": buffers or []})


@pytest.fixture
def fake_comm(monkeypatch):
    created = {}

    def _create(target_name, data, metadata, buffers):
        c = FakeComm(target_name, data, metadata, buffers)
        created["comm"] = c
        return c

    monkeypatch.setattr(comm_pkg, "create_comm", _create)
    return created


def _widget(store, transport):
    return Widget(
        transport,
        get_state=lambda: dict(store),
        set_state=store.update,
        model_id="",
    )


def test_open_creates_comm_with_state_and_metadata(fake_comm):
    t = CommTransport()
    w = _widget({"value": 0, "_esm": "x"}, t)
    w.open()
    c = fake_comm["comm"]
    assert c.target_name == "jupyter.widget"
    assert c.open_metadata == {"version": "2.1.0"}
    assert c.open_data["state"]["_model_name"] == "AnyModel"
    assert t.comm_id == "fake-comm-123"


def test_send_state_uses_comm_send(fake_comm):
    store = {"value": 0}
    t = CommTransport()
    w = _widget(store, t)
    w.open()
    store["value"] = 9
    w.send_state()
    sent = fake_comm["comm"].sends[-1]["data"]
    assert sent["method"] == "update"
    assert sent["buffer_paths"] == []
    # A full send_state() carries anywidget's identity fields alongside the changed
    # state (cositos-k43): JupyterLab's reload-without-kernel-restart restore path
    # reads model_name/model_module off this exact update message.
    assert sent["state"]["value"] == 9
    assert sent["state"]["_model_name"] == "AnyModel"


def test_inbound_update_flows_to_set_state(fake_comm):
    store = {"value": 0}
    t = CommTransport()
    w = _widget(store, t)
    w.open()
    fake_comm["comm"].receive({"method": "update", "state": {"value": 7}, "buffer_paths": []})
    assert store["value"] == 7


def test_request_state_triggers_update(fake_comm):
    t = CommTransport()
    w = _widget({"value": 5}, t)
    w.open()
    fake_comm["comm"].receive({"method": "request_state"})
    assert fake_comm["comm"].sends[-1]["data"]["state"]["value"] == 5


def test_close_closes_comm(fake_comm):
    t = CommTransport()
    w = _widget({"value": 0}, t)
    w.open()
    w.close()
    assert fake_comm["comm"].closed


def test_on_message_registered_before_open_is_bound_on_open(fake_comm):
    # Directly exercise the pending-callback path (Widget.open registers after open,
    # but a host may wire a handler first).
    t = CommTransport()
    received = []
    t.on_message(lambda data, buffers: received.append(data))
    t.send("comm_open", {"state": {}, "buffer_paths": []}, metadata={"version": "2.1.0"})
    fake_comm["comm"].receive({"method": "custom", "content": 1})
    assert received == [{"method": "custom", "content": 1}]
