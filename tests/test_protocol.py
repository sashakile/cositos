"""Tests for protocol message builders and the inbound parser."""

import pytest

from cositos import protocol
from cositos.protocol import (
    Custom,
    RequestState,
    Update,
    build_comm_open,
    build_custom,
    build_update,
    parse_message,
)


def test_comm_open_includes_immutable_anywidget_fields():
    data, buffers, metadata = build_comm_open({"_esm": "export default {}", "value": 1})
    state = data["state"]
    assert state["_model_module"] == "anywidget"
    assert state["_model_name"] == "AnyModel"
    assert state["_view_name"] == "AnyView"
    assert state["_view_count"] is None
    assert state["value"] == 1
    assert state["_esm"] == "export default {}"
    assert data["buffer_paths"] == []
    assert buffers == []
    assert metadata == {"version": "2.1.0"}


def test_comm_open_splits_buffers():
    data, buffers, _ = build_comm_open({"img": b"PNG"})
    assert "img" not in data["state"]
    assert data["buffer_paths"] == [["img"]]
    assert buffers == [b"PNG"]


def test_build_update_shape():
    data, buffers = build_update({"value": 2})
    assert data == {"method": "update", "state": {"value": 2}, "buffer_paths": []}
    assert buffers == []


def test_build_custom_shape():
    assert build_custom({"kind": "ping"}) == {"method": "custom", "content": {"kind": "ping"}}


def test_parse_update():
    msg = parse_message({"method": "update", "state": {"a": 1}, "buffer_paths": []})
    assert msg == Update(state={"a": 1}, buffer_paths=[])


def test_parse_request_state():
    assert parse_message({"method": "request_state"}) == RequestState()


def test_parse_custom():
    assert parse_message({"method": "custom", "content": 42}) == Custom(content=42)


def test_parse_unknown_method_raises():
    with pytest.raises(ValueError, match="Unrecognized"):
        parse_message({"method": "bogus"})


def test_mimebundle_shape():
    bundle = protocol.mimebundle("abc123")
    view = bundle[protocol.WIDGET_VIEW_MIMETYPE]
    assert view == {"version_major": 2, "version_minor": 1, "model_id": "abc123"}
