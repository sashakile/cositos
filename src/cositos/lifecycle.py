"""Pure widget lifecycle reducer — a `reduce(phase, event, state, capabilities) → (new_phase, effects[])` function.

The widget lifecycle is encoded as a deterministic state machine with three phases
(Unopened, Open, Closed), six event types, and five effect types. The reducer is a
pure function: no I/O, no side effects, no mutable state. It is fixture-testable
against ``fixtures/lifecycle/*.json``.

Usage
-----
    >>> from cositos.lifecycle import reduce, Phase, Open, TransportCapabilities
    >>> phase, effects = reduce(Phase.UNOPENED, Open(), {}, TransportCapabilities())
    >>> phase
    <Phase.OPEN: 'open'>
    >>> effects
    [Send(msg_type='comm_open', ...), Listen()]
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------

class Phase(Enum):
    """The three phases of a widget's lifecycle."""
    UNOPENED = "unopened"
    OPEN = "open"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Transport capabilities
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class TransportCapabilities:
    """Declares which event kinds the transport can carry.

    The reducer uses these flags to decide which effects to produce — the shell
    never blocks or rewrites events based on capabilities.
    """
    supports_receive: bool = True
    supports_request_state: bool = True
    supports_custom: bool = True
    supports_buffers: bool = True


# ---------------------------------------------------------------------------
# Effect types
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Send:
    """Send a Jupyter comm message to the frontend."""
    msg_type: str  # "comm_open" | "comm_msg" | "comm_close"
    data: dict[str, Any]
    buffers: list[Any] = dataclasses.field(default_factory=list)
    metadata: dict[str, Any] | None = None


@dataclasses.dataclass(frozen=True)
class Listen:
    """Register an inbound message callback on the transport."""
    pass


@dataclasses.dataclass(frozen=True)
class ApplyState:
    """Apply an inbound state dict to the host object."""
    state: dict[str, Any]


@dataclasses.dataclass(frozen=True)
class InvokeCustom:
    """Invoke the host's custom message handler."""
    content: Any
    buffers: list[Any] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Error:
    """An error effect — the shell shall raise RuntimeError in response."""
    message: str


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Open:
    """User/host wants to open the comm."""
    pass


@dataclasses.dataclass(frozen=True)
class SendState:
    """User/host wants to send an update with optional include filter."""
    include: set[str] | None = None


@dataclasses.dataclass(frozen=True)
class SendCustom:
    """User/host wants to send a custom message."""
    content: Any
    buffers: list[Any] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Inbound:
    """An inbound message arrived from the transport, with buffers already merged."""
    message: dict[str, Any]  # pre-parsed by parse_message
    buffers: list[Any] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Close:
    """User/host wants to close the comm."""
    pass


@dataclasses.dataclass(frozen=True)
class CommIdAssigned:
    """The transport assigned a comm id after a comm_open send."""
    id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _model_identity(version: str = "~0.11.*") -> dict[str, Any]:
    return {
        "_model_module": "anywidget",
        "_model_name": "AnyModel",
        "_model_module_version": version,
    }


def _view_identity(version: str = "~0.11.*") -> dict[str, Any]:
    return {
        "_view_module": "anywidget",
        "_view_name": "AnyView",
        "_view_module_version": version,
        "_view_count": None,
    }


def _immutable_fields(version: str = "~0.11.*") -> dict[str, Any]:
    return {**_model_identity(version), **_view_identity(version)}


# ---------------------------------------------------------------------------
# Reducer
# ---------------------------------------------------------------------------

def reduce(
    phase: Phase,
    event: Any,
    current_state: dict[str, Any],
    capabilities: TransportCapabilities,
) -> tuple[Phase, list[Any]]:
    """Pure widget lifecycle reducer.

    Parameters
    ----------
    phase:
        The current phase of the widget.
    event:
        An event instance (``Open``, ``SendState``, ``SendCustom``, ``Inbound``,
        ``Close``, or ``CommIdAssigned``).
    current_state:
        The current host widget state dict.
    capabilities:
        The transport's capability flags.

    Returns
    -------
    (new_phase, effects):
        The new phase and a list of effects to execute.
    """
    if isinstance(event, Open):
        return _reduce_open(phase, current_state, capabilities)
    elif isinstance(event, SendState):
        return _reduce_send_state(phase, event, current_state, capabilities)
    elif isinstance(event, SendCustom):
        return _reduce_send_custom(phase, event, capabilities)
    elif isinstance(event, Inbound):
        return _reduce_inbound(phase, event, current_state, capabilities)
    elif isinstance(event, Close):
        return _reduce_close(phase)
    elif isinstance(event, CommIdAssigned):
        return Phase.OPEN, []  # shell stores the id; no effects needed
    else:
        return phase, [Error(f"unknown event type: {type(event).__name__}")]


def _reduce_open(
    phase: Phase,
    current_state: dict[str, Any],
    capabilities: TransportCapabilities,
) -> tuple[Phase, list[Any]]:
    if phase == Phase.UNOPENED or phase == Phase.CLOSED:
        from cositos import protocol
        data, buffers, metadata = protocol.build_comm_open(
            {**_immutable_fields(), **current_state}
        )
        effects: list[Any] = [
            Send(msg_type="comm_open", data=data, buffers=buffers, metadata=metadata),
        ]
        if capabilities.supports_receive:
            effects.append(Listen())
        return Phase.OPEN, effects
    # Idempotent: already open, no-op
    return Phase.OPEN, []


def _reduce_send_state(
    phase: Phase,
    event: SendState,
    current_state: dict[str, Any],
    capabilities: TransportCapabilities,
) -> tuple[Phase, list[Any]]:
    if phase != Phase.OPEN:
        return phase, [Error("send_state() requires an open comm; call open() first")]
    if event.include is None:
        state = {**_immutable_fields(), **current_state}
    else:
        state = {k: v for k, v in current_state.items() if k in event.include}
    from cositos import protocol
    data, buffers = protocol.build_update(state)
    return phase, [Send(msg_type="comm_msg", data=data, buffers=buffers)]


def _reduce_send_custom(
    phase: Phase,
    event: SendCustom,
    capabilities: TransportCapabilities,
) -> tuple[Phase, list[Any]]:
    if phase != Phase.OPEN:
        return phase, [Error("send_custom() requires an open comm; call open() first")]
    if not capabilities.supports_custom:
        return phase, [Error("custom messages are not supported by this transport")]
    if not capabilities.supports_buffers and event.buffers:
        return phase, [Error("buffers are not supported by this transport")]
    from cositos import protocol
    data = protocol.build_custom(event.content)
    return phase, [
        Send(msg_type="comm_msg", data=data, buffers=event.buffers or [])
    ]


def _reduce_inbound(
    phase: Phase,
    event: Inbound,
    current_state: dict[str, Any],
    capabilities: TransportCapabilities,
) -> tuple[Phase, list[Any]]:
    # Inbound from closed or unopened: silently drop or buffer
    if phase != Phase.OPEN:
        return phase, []
    from cositos import protocol
    message = protocol.parse_message(event.message)
    if isinstance(message, protocol.Update):
        from cositos.buffers import put_buffers
        state = dict(message.state)
        put_buffers(state, message.buffer_paths, event.buffers)
        return phase, [ApplyState(state=state)]
    elif isinstance(message, protocol.RequestState):
        if not capabilities.supports_request_state:
            return phase, []
        return _reduce_send_state(phase, SendState(), current_state, capabilities)
    elif isinstance(message, protocol.Custom):
        return phase, [InvokeCustom(content=message.content, buffers=event.buffers)]
    else:
        # Ignored / unknown: no-op
        return phase, []


def _reduce_close(phase: Phase) -> tuple[Phase, list[Any]]:
    if phase == Phase.OPEN:
        return Phase.CLOSED, [Send(msg_type="comm_close", data={})]
    return phase, []