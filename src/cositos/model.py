"""The ``Widget`` façade: wires a host state object to a Transport using the core.

Deliberately minimal — no observer autodetection. The host decides when state changed
and calls :meth:`send_state`. Mirrors the Deno ``Comm`` and Python ``ReprMimeBundle``
responsibilities, minus per-language ergonomics.
"""

from __future__ import annotations

from typing import Any, Callable

from cositos import protocol
from cositos.buffers import put_buffers
from cositos.transport import Transport


class Widget:
    """Drive one anywidget-compatible widget over a Transport.

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
    """

    def __init__(
        self,
        transport: Transport,
        get_state: Callable[[], dict],
        set_state: Callable[[dict], None] | None = None,
        model_id: str = "",
    ) -> None:
        self._transport = transport
        self._get_state = get_state
        self._set_state = set_state
        self.model_id = model_id
        self._opened = False

    def open(self) -> None:
        """Send the ``comm_open`` and start listening for inbound messages."""
        data, buffers, metadata = protocol.build_comm_open(self._get_state())
        self._transport.send("comm_open", data, buffers=buffers, metadata=metadata)
        self._opened = True
        if getattr(self._transport, "supports_receive", False):
            self._transport.on_message(self._handle)

    def send_state(self, include: set[str] | None = None) -> None:
        """Send an ``update`` with the full state, or only ``include`` keys."""
        state = self._get_state()
        if include is not None:
            state = {k: v for k, v in state.items() if k in include}
        data, buffers = protocol.build_update(state)
        self._transport.send("comm_msg", data, buffers=buffers)

    def _handle(self, data: dict, buffers: list[Any]) -> None:
        """Dispatch an inbound message from the frontend."""
        message = protocol.parse_message(data)
        if isinstance(message, protocol.Update):
            if self._set_state is not None:
                state = dict(message.state)
                put_buffers(state, message.buffer_paths, buffers)
                self._set_state(state)
        elif isinstance(message, protocol.RequestState):
            self.send_state()
        # Custom messages are surfaced by hosts that need them (out of v0 scope).

    def mimebundle(self, repr_text: str = "") -> dict:
        """Return the widget-view mimebundle for display."""
        return protocol.mimebundle(self.model_id, repr_text)

    def close(self) -> None:
        """Close the comm channel."""
        if self._opened:
            self._transport.send("comm_close", {})
            self._opened = False
