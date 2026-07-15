"""The ``Widget`` façade: wires a host state object to a Transport using the core.

Deliberately minimal — no observer autodetection. The host decides when state changed
and calls :meth:`send_state`. Mirrors the Deno ``Comm`` and Python ``ReprMimeBundle``
responsibilities, minus per-language ergonomics.

Internally delegates to :class:`~cositos.lifecycle.WidgetShell`, which uses the pure
``reduce`` function. The public API is unchanged.
"""

from __future__ import annotations

from typing import Any, Callable

from cositos.lifecycle import WidgetShell
from cositos.transport import Transport


class Widget:
    """Drive one anywidget-compatible widget over a Transport.

    Internally delegates to :class:`~cositos.lifecycle.WidgetShell`.

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
        get_state: Callable[[], dict[str, Any]],
        set_state: Callable[[dict[str, Any]], None] | None = None,
        model_id: str = "",
        on_custom: Callable[[Any, list[Any]], None] | None = None,
    ) -> None:
        self._shell = WidgetShell(
            transport=transport,
            get_state=get_state,
            set_state=set_state,
            model_id=model_id,
            on_custom=on_custom,
        )
        self.model_id = model_id  # kept for backward compat; _shell.model_id is the source

    @property
    def _opened(self) -> bool:
        from cositos.lifecycle import Phase

        return self._shell._phase == Phase.OPEN

    @_opened.setter
    def _opened(self, value: bool) -> None:
        # Compatibility shim for tests that set _opened directly.
        # Only used for resetting state; the shell is the source of truth.
        from cositos.lifecycle import Phase

        if not value:
            self._shell._phase = Phase.UNOPENED

    def open(self) -> None:
        """Send the ``comm_open`` and start listening for inbound messages.

        Idempotent: a second call while already open is a no-op (no duplicate
        ``comm_open``), matching :meth:`close`.
        """
        self._shell.open()
        self.model_id = self._shell.model_id

    def send_state(self, include: set[str] | None = None) -> None:
        """Send an ``update`` with the full state, or only ``include`` keys.

        Requires an open comm; call :meth:`open` (or display the widget) first.
        """
        self._shell.send_state(include=include)

    def send_custom(self, content: Any, buffers: list[Any] | None = None) -> None:
        """Send a ``custom`` message to the frontend (``model.on('msg:custom')``).

        Requires an open comm; call :meth:`open` (or display the widget) first.
        """
        self._shell.send_custom(content, buffers=buffers)

    def mimebundle(self, repr_text: str = "") -> dict[str, Any]:
        """Return the widget-view mimebundle for display."""
        return self._shell.mimebundle(repr_text)

    def _repr_mimebundle_(self, include: Any = None, exclude: Any = None) -> dict[str, Any]:
        """Display hook: rendering the widget opens its comm, then returns the view bundle."""
        return self._shell._repr_mimebundle_(include, exclude)

    def close(self) -> None:
        """Close the comm channel."""
        self._shell.close()
