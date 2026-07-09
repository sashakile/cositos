"""A real, unmodified ``@jupyter-widgets/controls``/``base`` catalog — an optional extension.

cositos' anti-goal is *reimplementing* the ipywidgets widget zoo (``docs/widgets.md``);
this module does not reimplement it. It reuses the real frontend verbatim by building
:data:`~cositos.serialize.ModelEntry` state dicts that carry the zoo's own identity
(``_model_name``/``_model_module``/``_view_name``/``_view_module`` etc., pinned at module
version ``2.0.0`` — the same choice already made by ``examples/composition/build.py``).
``cositos.protocol.build_comm_open``/``cositos.model.Widget.send_state`` already merge
``{**anywidget_defaults, **state}``, so a caller-supplied real-widget identity reaches the
wire with zero core changes
(``.wai/projects/cositos-core/research/2026-07-09-research-real-controls-widgets-as-optional-extension.md``,
findings 1–3).

Scope is intentionally trimmed (YAGNI) to exactly ``IntSlider``, ``Dropdown``, ``VBox``,
``HBox`` and their required companion models — see
``.wai/projects/cositos-core/designs/2026-07-09-design-controls-catalog-schema-and-scope.md``
for the full catalog schema and the id-uniqueness rule this module implements (every call
mints fresh companion-model ids; the catalog's own placeholder strings are never reused as
real ids — :func:`cositos.serialize.dump_document` rejects duplicate ``model_id``s).

**No ``ipywidgets``/``anywidget`` Python package is required.** This module builds plain
state dicts from a static JSON catalog (``fixtures/controls-catalog.json``) plus the
stdlib (``json``, ``uuid``) — it never imports either package (see
``tests/test_contrib_controls.py::test_module_imports_no_optional_widget_packages`` for
the automated guard). Manually re-verified 2026-07-09 in a fresh venv with neither
``ipywidgets`` nor ``anywidget`` installed (``pip install -e .`` only): building and
serializing an ``int_slider``/``vbox`` tree through :func:`cositos.serialize.dump_document`
and :func:`cositos.embed.embed_html` succeeded.

**Deliberately exempt from an OpenSpec requirement.** This mirrors
:mod:`cositos.contrib.harvest`, the existing contrib precedent: contrib modules are
optional, additive wrappers over the pure core (already OpenSpec-covered under
``openspec/specs/{embed,protocol,serialization}``) and do not themselves gain a spec.

**Correction to the design note, found by the real-browser check this ticket's acceptance
criteria required (not by reading the source alone):** ``Dropdown``'s ``options``,
``value``, and ``label`` traits carry no ``sync=True`` tag in ipywidgets
(``widget_selection.py``) — only ``_options_labels`` (label strings) and ``index`` are on
the wire. A first catalog draft that put ``options``/``value`` straight into state
rendered an empty, unselectable ``<select>`` in a real browser; :func:`dropdown` below
translates its ergonomic ``options``/``value`` parameters into the real
``_options_labels``/``index`` wire fields.

**Accepted, documented risk (unresolved from the research note):** the pinned
``2.0.0`` module version for ``@jupyter-widgets/controls``/``base`` is verified against
the CDN ``@jupyter-widgets/html-manager`` (static export) and a bare subprocess
``ipykernel`` comm (live kernel) — *not* against a real, currently-installed JupyterLab's
bundled ``@jupyter-widgets`` frontend extension version. Treat that combination as an
open risk specifically for the live-in-JupyterLab case until it is checked.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from cositos.serialize import ModelEntry

__all__ = ["int_slider", "dropdown", "vbox", "hbox"]

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "controls-catalog.json"
)


def _load_catalog() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text())  # type: ignore[no-any-return]


_CATALOG = _load_catalog()


def _mint_id(root_id: str, role: str) -> str:
    return f"{root_id}-{role}"


def _identity(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "_model_name": spec["model_name"],
        "_model_module": spec["model_module"],
        "_model_module_version": spec["model_module_version"],
        "_view_name": spec["view_name"],
        "_view_module": spec["view_module"],
        "_view_module_version": spec["view_module_version"],
    }


def _build(
    catalog_key: str,
    overrides: dict[str, Any],
    *,
    model_id: str | None = None,
) -> list[ModelEntry]:
    """Build one catalog entry's widget + its freshly id'd companion models.

    The widget's own entry is always first in the returned list, followed by one entry
    per companion (order matches the catalog's ``companions`` list). Every companion gets
    a fresh id derived from this call's root id — never the catalog's literal
    placeholder string — per the design note's id-uniqueness rule.
    """
    spec = _CATALOG[catalog_key]
    root_id = model_id or uuid.uuid4().hex

    state = dict(spec["default_state"])
    companion_entries: list[ModelEntry] = []
    for companion in spec["companions"]:
        key = companion["key_in_default_state"]
        companion_id = _mint_id(root_id, key)
        state[key] = f"IPY_MODEL_{companion_id}"
        companion_state = {
            "_model_name": companion["model_name"],
            "_model_module": companion["model_module"],
            "_model_module_version": companion["model_module_version"],
            "_view_name": companion["view_name"],
            "_view_module": companion["view_module"],
            "_view_module_version": companion["view_module_version"],
        }
        companion_entries.append((companion_id, companion_state))

    state.update(overrides)
    widget_state = {**_identity(spec), **state}
    return [(root_id, widget_state), *companion_entries]


def int_slider(value: int = 0, min: int = 0, max: int = 100, **overrides: Any) -> list[ModelEntry]:
    """A real ``@jupyter-widgets/controls`` ``IntSliderModel`` + its style/layout companions."""
    return _build("int_slider", {"value": value, "min": min, "max": max, **overrides})


def dropdown(options: Any, value: Any = None, **overrides: Any) -> list[ModelEntry]:
    """A real ``@jupyter-widgets/controls`` ``DropdownModel`` + its style/layout companions.

    ``options``/``value`` are the ergonomic, ipywidgets-``Dropdown``-constructor-shaped
    inputs; on the wire only ``_options_labels`` (the label strings) and ``index`` are
    synced traits (``Dropdown``'s own ``options``/``value``/``label`` traits carry no
    ``sync=True`` tag in ipywidgets' source — confirmed empirically: a naive catalog entry
    that put ``options``/``value`` straight into state rendered an empty, unselectable
    dropdown in a real browser). Pass ``index=`` directly in ``overrides`` to bypass the
    ``value``-to-``index`` lookup (e.g. when ``value`` is unhashable or repeated).
    """
    labels = [str(option) for option in options]
    index = overrides.pop("index", None)
    if index is None and value is not None:
        str_value = str(value)
        index = labels.index(str_value) if str_value in labels else None
    return _build("dropdown", {"_options_labels": labels, "index": index, **overrides})


def _box(catalog_key: str, children: list[list[ModelEntry]], **overrides: Any) -> list[ModelEntry]:
    child_refs = [f"IPY_MODEL_{child[0][0]}" for child in children]
    own = _build(catalog_key, {"children": child_refs, **overrides})
    descendants = [entry for child in children for entry in child]
    return own + descendants


def vbox(children: list[list[ModelEntry]], **overrides: Any) -> list[ModelEntry]:
    """A real ``@jupyter-widgets/controls`` ``VBoxModel`` laying out ``children`` vertically.

    ``children`` is a list of previously built entries-lists (e.g. the output of
    :func:`int_slider`/:func:`dropdown`/:func:`vbox`/:func:`hbox`) — this widget's
    ``children`` trait references each child's root id, and the returned entries list
    flattens in every descendant so the whole tree serializes as one document.
    """
    return _box("vbox", children, **overrides)


def hbox(children: list[list[ModelEntry]], **overrides: Any) -> list[ModelEntry]:
    """A real ``@jupyter-widgets/controls`` ``HBoxModel`` laying out ``children`` horizontally.

    See :func:`vbox` for the ``children`` composition contract (identical, horizontal
    layout only).
    """
    return _box("hbox", children, **overrides)
