"""Static-HTML export: render a serialized widget :data:`Document` to a self-contained page.

Reuses the stock ipywidgets embed format \u2014 a ``application/vnd.jupyter.widget-state+json``
block plus per-view ``widget-view+json`` scripts \u2014 rendered by the CDN-hosted
``@jupyter-widgets/html-manager``. The anywidget model/view module resolves from jsDelivr
at render time, so no frontend is bundled and no kernel is needed to display a saved UI.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from cositos.serialize import Document

STATE_MIMETYPE = "application/vnd.jupyter.widget-state+json"
VIEW_MIMETYPE = "application/vnd.jupyter.widget-view+json"

_DEFAULT_HTML_MANAGER_VERSION = "1"
_REQUIREJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.3.4/require.min.js"
_EMBED_AMD_URL = "https://cdn.jsdelivr.net/npm/@jupyter-widgets/html-manager@{v}/dist/embed-amd.js"
_EMBED_URL = "https://cdn.jsdelivr.net/npm/@jupyter-widgets/html-manager@{v}/dist/embed.js"

# Neutralise the only sequences that can break out of a <script> element, per
# https://html.spec.whatwg.org/multipage/scripting.html#restrictions-for-contents-of-script-elements
_SCRIPT_ESCAPE = re.compile(r"<(script|/script|!--)", re.IGNORECASE)


def _escape_script(text: str) -> str:
    return _SCRIPT_ESCAPE.sub(r"\\u003c\1", text)


def embed_snippet(
    document: Document,
    *,
    views: Iterable[str] | None = None,
    requirejs: bool = True,
    html_manager_version: str = _DEFAULT_HTML_MANAGER_VERSION,
) -> str:
    """Render the embed *snippet* (loader + state + view scripts), without an HTML wrapper.

    Use this to drop a widget into an existing page (a Quarto/blog cell, a template). See
    :func:`embed_html` for a complete standalone page.
    """
    model_ids = list(views) if views is not None else list(document.get("state", {}))
    state_block = _escape_script(json.dumps(document, indent=2))
    view_blocks = "\n".join(
        f'<script type="{VIEW_MIMETYPE}">\n'
        + _escape_script(json.dumps({"version_major": 2, "version_minor": 0, "model_id": mid}))
        + "\n</script>"
        for mid in model_ids
    )
    loader = _loader(requirejs, html_manager_version)
    return f'{loader}\n<script type="{STATE_MIMETYPE}">\n{state_block}\n</script>\n{view_blocks}\n'


def embed_html(
    document: Document,
    *,
    views: Iterable[str] | None = None,
    title: str = "cositos widgets",
    requirejs: bool = True,
    html_manager_version: str = _DEFAULT_HTML_MANAGER_VERSION,
) -> str:
    """Render ``document`` (a :func:`cositos.serialize.dump_document` result) to a full page.

    ``views`` selects which model ids get a rendered view (default: every model in the
    document). The full state is always embedded so cross-widget references resolve.
    """
    snippet = embed_snippet(
        document, views=views, requirejs=requirejs, html_manager_version=html_manager_version
    )
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '    <meta charset="UTF-8">\n'
        f"    <title>{title}</title>\n"
        "</head>\n<body>\n"
        f"{snippet}"
        "</body>\n</html>\n"
    )


def write_html(path: str | Path, document: Document, **kwargs: Any) -> None:
    """Write :func:`embed_html` output for ``document`` to ``path``."""
    Path(path).write_text(embed_html(document, **kwargs))


def _loader(requirejs: bool, version: str) -> str:
    embed_url = (_EMBED_AMD_URL if requirejs else _EMBED_URL).format(v=version)
    script = f'<script src="{embed_url}" crossorigin="anonymous"></script>'
    if requirejs:
        return f'<script src="{_REQUIREJS_URL}" crossorigin="anonymous"></script>\n{script}'
    return script
