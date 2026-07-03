"""Tests for the Widget façade against an in-memory fake transport."""

from cositos.model import Widget


class FakeTransport:
    supports_receive = True

    def __init__(self):
        self.sent = []
        self._cb = None

    def send(self, msg_type, content, buffers=None, metadata=None):
        self.sent.append((msg_type, content, buffers or [], metadata))

    def on_message(self, callback):
        self._cb = callback

    def deliver(self, data, buffers=None):
        self._cb(data, buffers or [])


def make_widget(initial):
    store = dict(initial)
    t = FakeTransport()
    w = Widget(t, get_state=lambda: dict(store), set_state=store.update, model_id="m1")
    return w, t, store


def test_open_sends_comm_open_with_metadata():
    w, t, _ = make_widget({"_esm": "x", "value": 0})
    w.open()
    msg_type, content, _buffers, metadata = t.sent[0]
    assert msg_type == "comm_open"
    assert metadata == {"version": "2.1.0"}
    assert content["state"]["_model_name"] == "AnyModel"


def test_send_state_emits_update():
    w, t, store = make_widget({"value": 0})
    w.open()
    store["value"] = 7
    w.send_state()
    msg_type, content, _b, _m = t.sent[-1]
    assert msg_type == "comm_msg"
    assert content["method"] == "update"
    assert content["state"]["value"] == 7


def test_inbound_update_applies_state():
    w, t, store = make_widget({"value": 0})
    w.open()
    t.deliver({"method": "update", "state": {"value": 99}, "buffer_paths": []})
    assert store["value"] == 99


def test_request_state_triggers_full_update():
    w, t, _ = make_widget({"value": 5})
    w.open()
    t.deliver({"method": "request_state"})
    msg_type, content, _b, _m = t.sent[-1]
    assert msg_type == "comm_msg"
    assert content["state"]["value"] == 5


def test_inbound_update_merges_buffers():
    w, t, store = make_widget({"img": None})
    w.open()
    t.deliver({"method": "update", "state": {}, "buffer_paths": [["img"]]}, buffers=[b"PNG"])
    assert store["img"] == b"PNG"


def test_send_custom_emits_custom_message():
    w, t, _ = make_widget({"value": 0})
    w.open()
    w.send_custom({"kind": "ping"})
    msg_type, content, _b, _m = t.sent[-1]
    assert msg_type == "comm_msg"
    assert content == {"method": "custom", "content": {"kind": "ping"}}


def test_inbound_custom_invokes_callback():
    received = []
    t = FakeTransport()
    w = Widget(t, get_state=lambda: {}, on_custom=lambda c, b: received.append((c, b)))
    w.open()
    t.deliver({"method": "custom", "content": {"kind": "pong"}}, buffers=[b"x"])
    assert received == [({"kind": "pong"}, [b"x"])]
