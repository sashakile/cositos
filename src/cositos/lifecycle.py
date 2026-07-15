"""Pure widget lifecycle reducer: `reduce(phase, event, state, caps) -> (new_phase, effects[])`.

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
from typing import Any, Callable

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


# ---------------------------------------------------------------------------
# Imperative Shell
# ---------------------------------------------------------------------------


class WidgetShell:
    """Thin imperative shell that calls ``reduce`` and executes effects.

    Mirrors the existing ``Widget`` class API so existing end-user code continues
    to work without changes. The shell owns the event loop: it holds the current
    phase, the host state (fetched via ``get_state``), and the capability flags,
    feeds them into ``reduce``, and walks the returned effects.

    Parameters
    ----------
    transport:
        The kernel comm adapter.
    get_state:
        Returns the current full state dict (including ``_esm``).
    set_state:
        Applies an inbound state dict to the host object. Optional; if omitted,
        inbound ``update`` messages are ignored.
    model_id:
        The comm id, for the display mimebundle.
    on_custom:
        Callback invoked with ``(content, buffers)`` for inbound custom messages.
        Optional; if omitted, inbound custom messages are ignored.
    capabilities:
        Transport capability flags. Defaults to full capability.
    """

    def __init__(
        self,
        transport: Any,
        get_state: Callable[[], dict[str, Any]],
        set_state: Callable[[dict[str, Any]], None] | None = None,
        model_id: str = "",
        on_custom: Callable[[Any, list[Any]], None] | None = None,
        capabilities: TransportCapabilities | None = None,
    ):
        self._transport = transport
        self._get_state = get_state
        self._set_state = set_state
        self._on_custom = on_custom
        caps = capabilities
        if caps is None:
            # Infer from transport attributes
            caps = TransportCapabilities(
                supports_receive=getattr(transport, "supports_receive", False),
                supports_request_state=getattr(transport, "supports_request_state", True),
                supports_custom=getattr(transport, "supports_custom", True),
                supports_buffers=getattr(transport, "supports_buffers", True),
            )
        self._capabilities = caps
        self._phase: Phase = Phase.UNOPENED
        self.model_id = model_id
        self._listening = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Send the ``comm_open`` and start listening for inbound messages.

        Idempotent: a second call while already open is a no-op (no duplicate
        ``comm_open``), matching :meth:`close`.
        """
        if self._phase == Phase.OPEN:
            return
        self._execute(reduce(self._phase, Open(), self._get_state(), self._capabilities))

    def send_state(self, include: set[str] | None = None) -> None:
        """Send an ``update`` with the full state, or only ``include`` keys.

        Requires an open comm; call :meth:`open` (or display the widget) first.
        """
        self._execute(
            reduce(self._phase, SendState(include=include), self._get_state(), self._capabilities)
        )

    def send_custom(self, content: Any, buffers: list[Any] | None = None) -> None:
        """Send a ``custom`` message to the frontend (``model.on('msg:custom')``).

        Requires an open comm; call :meth:`open` (or display the widget) first.
        """
        self._execute(
            reduce(
                self._phase,
                SendCustom(content=content, buffers=buffers or []),
                self._get_state(),
                self._capabilities,
            )
        )

    def close(self) -> None:
        """Close the comm channel. Idempotent."""
        self._execute(reduce(self._phase, Close(), {}, self._capabilities))

    def mimebundle(self, repr_text: str = "") -> dict[str, Any]:
        """Return the widget-view mimebundle for display."""
        from cositos import protocol
        return protocol.mimebundle(self.model_id, repr_text)

    def _repr_mimebundle_(self, include: Any = None, exclude: Any = None) -> dict[str, Any]:
        """Display hook: rendering the widget opens its comm, then returns the view bundle."""
        if self._phase == Phase.UNOPENED or self._phase == Phase.CLOSED:
            self.open()
        return self.mimebundle()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute(self, result: tuple[Phase, list[Any]]) -> None:
        """Walk the effect list from a ``reduce`` call and execute each effect."""
        new_phase, effects = result
        self._phase = new_phase
        for effect in effects:
            self._exec_one(effect)

    def _exec_one(self, effect: Any) -> None:
        """Execute a single effect."""
        if isinstance(effect, Send):
            self._transport.send(
                effect.msg_type,
                effect.data,
                buffers=effect.buffers,
                metadata=effect.metadata,
            )
            # Comm-id feedback loop: after a comm_open, adopt the transport's id
            if effect.msg_type == "comm_open":
                cid = getattr(self._transport, "comm_id", "")
                if cid:
                    self.model_id = cid
                    self._execute(
                        reduce(self._phase, CommIdAssigned(id=cid), {}, self._capabilities)
                    )
        elif isinstance(effect, Listen):
            if not self._listening:
                self._transport.on_message(self._handle_inbound)
                self._listening = True
        elif isinstance(effect, ApplyState):
            if self._set_state is not None:
                self._set_state(effect.state)
        elif isinstance(effect, InvokeCustom):
            if self._on_custom is not None:
                self._on_custom(effect.content, effect.buffers)
        elif isinstance(effect, Error):
            raise RuntimeError(effect.message)

    def _handle_inbound(self, data: dict[str, Any], buffers: list[Any]) -> None:
        """Dispatch an inbound message from the transport back into ``reduce``."""
        from cositos import protocol
        message = protocol.parse_message(data)
        if isinstance(message, (protocol.Update, protocol.Custom, protocol.RequestState)):
            self._execute(
                reduce(
                    self._phase,
                    Inbound(message=data, buffers=buffers),
                    self._get_state(),
                    self._capabilities,
                )
            )
        else:
            # Ignored: forward-compat, no-op
            pass