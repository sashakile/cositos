"""Wrap an *existing* ipywidgets tree as a cositos :data:`~cositos.serialize.Document`.

The reuse insight this module packages: ``ipywidgets.embed.embed_data(views=[w])`` already
walks a widget and its transitive children and returns a ``manager_state`` that is, byte
for byte, a cositos v2 Widget-State :data:`~cositos.serialize.Document`. So any app or
library built on ipywidgets — including anywidget-based plotting widgets (plotly
``FigureWidget``, altair ``JupyterChart``) — can be serialized, round-tripped, and
statically embedded through cositos with **no core changes**. This is the thin,
Python-only, optional wrapper over that call; it never enters the pure core.

``embed_data`` is the current, supported entry point; the older ``Widget.widgets`` global
registry is deprecated and must not be used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cositos.embed import embed_html
from cositos.serialize import Document

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ipywidgets import Widget

__all__ = ["harvest", "harvest_html"]


def _embed_data(widgets: tuple[Any, ...]) -> dict[str, Any]:
    """Call ``ipywidgets.embed.embed_data`` for ``widgets`` with clear failures.

    Always passes ``drop_defaults=False``. ``embed_data``'s own default
    (``drop_defaults=True``) compares each synced trait's *current* value against its
    *class-level default* and omits it when they match — but a widget that bundles its
    own frontend commonly declares that content (``_esm``/``_css``) as the trait's class
    default rather than setting it per instance (Plotly's ``FigureWidget`` and Altair's
    ``JupyterChart`` both do this). ``drop_defaults=True`` then silently drops ``_esm``
    from the harvested state, and the CDN anywidget runtime's ``AnyView`` throws
    (``isHref(undefined)``) instead of rendering (cositos-b2t). ``harvest``'s own
    docstring promise — a verbatim capture — requires the non-dropping default anyway.

    Raises
    ------
    ImportError
        If ipywidgets is not installed (this is an optional dependency of contrib).
    ValueError
        If no widget was given (an empty document is never what a caller wants here).
    """
    if not widgets:
        raise ValueError("harvest requires at least one widget to serialize")
    try:
        from ipywidgets.embed import embed_data
    except ImportError as exc:  # pragma: no cover - exercised only without ipywidgets
        raise ImportError(
            "cositos.contrib.harvest requires ipywidgets; install it with "
            "`pip install ipywidgets` (or the cositos 'oracle' extra)"
        ) from exc
    data: dict[str, Any] = embed_data(views=list(widgets), drop_defaults=False)
    return data


def harvest(*widgets: Widget) -> Document:
    """Return a cositos :data:`~cositos.serialize.Document` for existing ipywidgets ``widgets``.

    Captures each widget and its transitive children (children are held by reference as
    ``"IPY_MODEL_<id>"`` strings, exactly like a natively built cositos document). The
    result round-trips through :func:`cositos.serialize.load_document` /
    :func:`~cositos.serialize.dump_document` and renders via
    :func:`cositos.embed.embed_html`.

    For static export prefer :func:`harvest_html`, which renders only the top-level
    widgets as views (a widget expands to extra layout/style models that have no view).
    """
    document: Document = _embed_data(widgets)["manager_state"]
    return document


def harvest_html(*widgets: Widget, **embed_kwargs: Any) -> str:
    """Serialize ``widgets`` and render them to a self-contained static HTML page.

    Only the passed top-level ``widgets`` become rendered views; their auxiliary
    layout/style models are embedded as state but not turned into (viewless) view scripts.
    ``embed_kwargs`` are forwarded to :func:`cositos.embed.embed_html` (e.g. ``title``).
    """
    data = _embed_data(widgets)
    view_ids = [spec["model_id"] for spec in data["view_specs"]]
    return embed_html(data["manager_state"], views=view_ids, **embed_kwargs)
