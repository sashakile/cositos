"""The Transport seam: the only kernel-facing interface the core depends on.

A host language supplies a concrete Transport (e.g. over the Python ``comm`` package,
``Deno.jupyter.broadcast``, or IJulia). The core never imports kernel code.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class Transport(Protocol):
    """Minimal comm transport.

    Implementations MUST send messages to the frontend and MAY receive them back.
    ``supports_receive`` lets the core degrade to one-way widgets on broadcast-only
    kernels (e.g. early Deno).
    """

    supports_receive: bool

    def send(
        self,
        msg_type: str,
        content: dict,
        buffers: list[Any] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Send a Jupyter comm message (``comm_open`` / ``comm_msg`` / ``comm_close``)."""
        ...

    def on_message(self, callback: Callable[[dict, list[Any]], None]) -> None:
        """Register a callback invoked with ``(data, buffers)`` for inbound messages."""
        ...
