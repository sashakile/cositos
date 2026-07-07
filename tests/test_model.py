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


def test_inbound_unknown_method_is_ignored():
    # Forward-compat (cositos-05i): an unrecognized inbound method must no-op, not raise
    # out of the comm dispatch callback, and must not touch host state.
    w, t, store = make_widget({"value": 7})
    w.open()
    t.deliver({"method": "echo_update", "state": {"value": 99}})
    t.deliver({"method": "bogus"})
    t.deliver({})  # missing method
    assert store["value"] == 7


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


def test_inbound_update_without_set_state_is_ignored():
    t = FakeTransport()
    w = Widget(t, get_state=lambda: {"value": 0})  # no set_state
    w.open()
    t.deliver({"method": "update", "state": {"value": 1}, "buffer_paths": []})
    # no crash, nothing to assert on state; the None-callback custom path is also a no-op
    t.deliver({"method": "custom", "content": 1})


def test_send_state_with_include_filters_keys():
    w, t, _ = make_widget({"a": 1, "b": 2, "_esm": "x"})
    w.open()
    w.send_state(include={"a"})
    _mt, content, _b, _m = t.sent[-1]
    assert content["state"] == {"a": 1}


def test_mimebundle_includes_repr_text():
    w, _t, _ = make_widget({"value": 0})
    bundle = w.mimebundle("Counter(value=0)")
    assert bundle["text/plain"] == "Counter(value=0)"


def test_close_sends_comm_close_once():
    w, t, _ = make_widget({"value": 0})
    w.open()
    w.close()
    assert t.sent[-1][0] == "comm_close"
    n = len(t.sent)
    w.close()  # idempotent — no second comm_close
    assert len(t.sent) == n


def test_open_is_idempotent():
    # Regression (cositos-und): a second open() must not send a duplicate comm_open.
    w, t, _ = make_widget({"_esm": "x", "value": 0})
    w.open()
    n = len(t.sent)
    w.open()
    assert len(t.sent) == n


def test_send_state_before_open_raises_clear_error():
    # A clear, documented error beats the transport's low-level 'comm not opened'.
    w, _t, _ = make_widget({"value": 0})
    try:
        w.send_state()
    except RuntimeError as e:
        assert "open" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError for send_state before open()")


def test_send_custom_before_open_raises_clear_error():
    w, _t, _ = make_widget({"value": 0})
    try:
        w.send_custom({"kind": "ping"})
    except RuntimeError as e:
        assert "open" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError for send_custom before open()")


class CommIdTransport(FakeTransport):
    """A transport that exposes a server-generated comm id, like CommTransport."""

    comm_id = "server-generated-id"


def test_open_syncs_model_id_from_transport_comm_id():
    store = {"_esm": "x", "value": 0}
    t = CommIdTransport()
    w = Widget(t, get_state=lambda: dict(store), model_id="ignored")
    w.open()
    assert w.model_id == "server-generated-id"


def test_open_keeps_model_id_when_transport_has_no_comm_id():
    w, _t, _ = make_widget({"value": 0})  # FakeTransport: no comm_id
    w.open()
    assert w.model_id == "m1"


def test_repr_mimebundle_auto_opens_and_returns_view_bundle():
    from cositos.protocol import WIDGET_VIEW_MIMETYPE

    w, t, _ = make_widget({"_esm": "x", "value": 0})
    bundle = w._repr_mimebundle_()
    assert t.sent[0][0] == "comm_open"  # displaying opens the comm
    assert bundle[WIDGET_VIEW_MIMETYPE]["model_id"] == "m1"


def test_repr_mimebundle_does_not_reopen_when_already_open():
    w, t, _ = make_widget({"value": 0})
    w.open()
    n = len(t.sent)
    w._repr_mimebundle_()
    assert len(t.sent) == n  # no second comm_open


def test_open_skips_on_message_when_transport_cannot_receive():
    # A broadcast-only transport (supports_receive=False, e.g. early Deno) must still
    # open the comm but must not register an inbound handler.
    class OneWayTransport:
        supports_receive = False

        def __init__(self) -> None:
            self.sent: list = []
            self.on_message_called = False

        def send(self, msg_type, content, buffers=None, metadata=None):
            self.sent.append((msg_type, content))

        def on_message(self, callback):
            self.on_message_called = True

    t = OneWayTransport()
    w = Widget(t, get_state=lambda: {"value": 1}, set_state=lambda d: None, model_id="m1")
    w.open()

    assert t.sent[0][0] == "comm_open"
    assert t.on_message_called is False
