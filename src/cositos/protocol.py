"""Widget messaging protocol constants, message builders, and the inbound parser.

Implements ipywidgets protocol v2.1.0. State carries anywidget's immutable model/view
fields so the published anywidget ``AnyModel``/``AnyView`` frontend renders the widget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cositos.buffers import remove_buffers

PROTOCOL_VERSION_MAJOR = 2
PROTOCOL_VERSION_MINOR = 1
PROTOCOL_VERSION = f"{PROTOCOL_VERSION_MAJOR}.{PROTOCOL_VERSION_MINOR}.0"

TARGET_NAME = "jupyter.widget"
WIDGET_VIEW_MIMETYPE = "application/vnd.jupyter.widget-view+json"

#: Default anywidget frontend semver range this backend targets. Kept in sync with a
#: released anywidget frontend; override per-widget if you pin a different frontend.
ANYWIDGET_MODULE_VERSION = "~0.11.*"

ESM_KEY = "_esm"
CSS_KEY = "_css"


def model_identity(version: str) -> dict[str, Any]:
    """anywidget's immutable *model* fields (schema-v2 top-level record identity)."""
    return {
        "_model_module": "anywidget",
        "_model_name": "AnyModel",
        "_model_module_version": version,
    }


def view_identity(version: str) -> dict[str, Any]:
    """anywidget's immutable *view* fields — the identity the html-manager needs to
    pick a view class. In schema v2 these live inside each model's ``state``.
    """
    return {
        "_view_module": "anywidget",
        "_view_name": "AnyView",
        "_view_module_version": version,
        "_view_count": None,
    }


def _immutable_fields(version: str) -> dict[str, Any]:
    return {**model_identity(version), **view_identity(version)}


def build_comm_open(
    state: dict[str, Any], anywidget_version: str = ANYWIDGET_MODULE_VERSION
) -> tuple[dict[str, Any], list[Any], dict[str, Any]]:
    """Build the ``comm_open`` payload.

    Returns ``(data, buffers, metadata)`` where ``data`` has ``state`` (with the
    immutable anywidget fields merged in) and ``buffer_paths``.
    """
    full = {**_immutable_fields(anywidget_version), **state}
    stripped, buffer_paths, buffers = remove_buffers(full)
    data = {"state": stripped, "buffer_paths": buffer_paths}
    metadata = {"version": PROTOCOL_VERSION}
    return data, buffers, metadata


def build_update(state: dict[str, Any]) -> tuple[dict[str, Any], list[Any]]:
    """Build an ``update`` (``comm_msg``) payload. Returns ``(data, buffers)``."""
    stripped, buffer_paths, buffers = remove_buffers(state)
    data = {"method": "update", "state": stripped, "buffer_paths": buffer_paths}
    return data, buffers


def build_custom(content: Any) -> dict[str, Any]:
    """Build a ``custom`` message payload (``comm_msg`` data)."""
    return {"method": "custom", "content": content}


def mimebundle(model_id: str, repr_text: str = "") -> dict[str, Any]:
    """Build the widget-view mimebundle used for display."""
    bundle: dict[str, Any] = {
        WIDGET_VIEW_MIMETYPE: {
            "version_major": PROTOCOL_VERSION_MAJOR,
            "version_minor": PROTOCOL_VERSION_MINOR,
            "model_id": model_id,
        },
    }
    if repr_text:
        bundle["text/plain"] = repr_text
    return bundle


@dataclass(frozen=True)
class Update:
    """Inbound state update from the frontend."""

    state: dict[str, Any]
    buffer_paths: list[Any]


@dataclass(frozen=True)
class RequestState:
    """Frontend requests the full widget state."""


@dataclass(frozen=True)
class Custom:
    """Inbound custom message."""

    content: Any


@dataclass(frozen=True)
class Ignored:
    """An inbound message cositos does not act on (unknown/missing ``method``).

    ipywidgets' ``Widget._handle_msg`` silently ignores methods it does not recognize
    (e.g. a newer frontend's ``echo_update``). Returning this benign sentinel instead of
    raising keeps a cositos widget forward-compatible and stops an unrecognized message
    from propagating out of the comm dispatch callback (cositos-05i).
    """

    method: Any = None


def parse_message(data: Any) -> Update | RequestState | Custom | Ignored:
    """Parse an inbound ``comm_msg`` ``data`` dict into a typed event.

    An unknown or missing ``method`` — or a non-dict ``data`` (malformed wire payload) —
    yields :class:`Ignored` (never raises), matching ipywidgets' forward-compatible
    dispatch: the caller no-ops on it.
    """
    if not isinstance(data, dict):
        return Ignored()
    method = data.get("method")
    if method == "update":
        return Update(state=data.get("state", {}), buffer_paths=data.get("buffer_paths", []))
    if method == "request_state":
        return RequestState()
    if method == "custom":
        return Custom(content=data.get("content"))
    return Ignored(method=method)
