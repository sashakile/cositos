"""Jupyter host adapter: a :class:`~cositos.transport.Transport` over the ``comm`` package.

This is the piece that plugs the pure protocol core into a real Jupyter kernel
(ipykernel, and anything else that provides ``comm``). It mirrors what
anywidget's ``open_comm``/``ReprMimeBundle`` do, but stays a thin Transport so the core
remains kernel-agnostic.

Usage in a kernel::

    from cositos import Widget
    from cositos.jupyter import CommTransport

    state = {"_esm": ESM, "value": 0}
    store = dict(state)
    widget = Widget(
        CommTransport(),
        get_state=lambda: dict(store),
        set_state=store.update,
    )
    widget.open()          # sends comm_open over the kernel's iopub
    widget.mimebundle()    # -> display via _repr_mimebundle_
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # pragma: no cover
    from comm.base_comm import BaseComm


class CommTransport:
    """Adapt the ``comm`` package to the cositos :class:`Transport` protocol.

    The comm is created lazily on the first ``comm_open`` send, carrying the initial
    state exactly as the protocol requires (no separate open + update round-trip).
    """

    supports_receive: bool = True

    def __init__(self) -> None:
        self._comm: BaseComm | None = None
        self._pending: Callable[[dict[str, Any], list[Any]], None] | None = None

    @property
    def comm_id(self) -> str:
        """The comm id (widget ``model_id``); empty until opened."""
        return self._comm.comm_id if self._comm is not None else ""

    def send(
        self,
        msg_type: str,
        content: dict[str, Any],
        buffers: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if msg_type == "comm_open":
            self._open(content, buffers or [], metadata or {})
        elif msg_type == "comm_msg":
            self._require_comm().send(data=content, buffers=buffers or None)
        elif msg_type == "comm_close":
            self._require_comm().close()
        else:  # pragma: no cover - defensive
            raise ValueError(f"Unknown comm message type: {msg_type!r}")

    def on_message(self, callback: Callable[[dict[str, Any], list[Any]], None]) -> None:
        if self._comm is None:
            # Registered before open() created the comm; wire it up on open.
            self._pending = callback
            return
        self._bind(callback)

    # -- internals -------------------------------------------------------------

    def _open(self, content: dict[str, Any], buffers: list[Any], metadata: dict[str, Any]) -> None:
        import comm  # noqa: PLC0415

        self._comm = comm.create_comm(
            target_name="jupyter.widget",
            data=content,
            metadata=metadata,
            buffers=buffers or None,
        )
        if self._pending is not None:
            self._bind(self._pending)
            self._pending = None

    def _bind(self, callback: Callable[[dict[str, Any], list[Any]], None]) -> None:
        def _on_msg(msg: dict[str, Any]) -> None:
            data = msg["content"]["data"]
            callback(data, msg.get("buffers", []))

        self._require_comm().on_msg(_on_msg)

    def _require_comm(self) -> BaseComm:
        if self._comm is None:  # pragma: no cover - defensive
            raise RuntimeError("comm not opened; call Widget.open() first")
        return self._comm
