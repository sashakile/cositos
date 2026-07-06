"""Tests for static-HTML export of a serialized widget Document (embed capability)."""

import json
import re

from cositos.embed import embed_html, write_html
from cositos.serialize import dump_document

VIEW_MIME = "application/vnd.jupyter.widget-view+json"
STATE_MIME = "application/vnd.jupyter.widget-state+json"


def _doc():
    return dump_document(
        [
            ("box", {"_esm": "export default {}", "children": ["IPY_MODEL_child"]}),
            ("child", {"value": 1}),
        ]
    )


def _script_json(html: str, mime: str) -> list[dict]:
    pattern = re.compile(r'<script type="' + re.escape(mime) + r'">\s*(.*?)\s*</script>', re.DOTALL)
    return [json.loads(m) for m in pattern.findall(html)]


def test_embeds_document_state_block() -> None:
    doc = _doc()
    html = embed_html(doc)
    (embedded,) = _script_json(html, STATE_MIME)
    assert embedded == doc


def test_emits_a_view_script_per_model() -> None:
    html = embed_html(_doc())
    views = _script_json(html, VIEW_MIME)
    ids = {v["model_id"] for v in views}
    assert ids == {"box", "child"}
    assert all(v["version_major"] == 2 and v["version_minor"] == 0 for v in views)


def test_views_argument_restricts_emitted_views() -> None:
    html = embed_html(_doc(), views=["child"])
    views = _script_json(html, VIEW_MIME)
    assert [v["model_id"] for v in views] == ["child"]
    # The full state is still embedded so the ref target resolves.
    assert set(_script_json(html, STATE_MIME)[0]["state"]) == {"box", "child"}


def test_includes_cdn_html_manager_loader() -> None:
    html = embed_html(_doc())
    assert "@jupyter-widgets/html-manager" in html
    assert "require" in html.lower()  # require.js by default


def test_embedded_json_is_script_escaped() -> None:
    doc = dump_document([("m", {"html": "<b>hi</b></script><!-- x"})])
    html = embed_html(doc)
    assert "</script><!--" not in html  # breakout sequence neutralised
    # \u003c is a valid JSON escape for '<', so the block still parses back to the doc.
    assert _script_json(html, STATE_MIME)[0] == doc


def test_non_requirejs_uses_embed_js_without_requirejs() -> None:
    html = embed_html(_doc(), requirejs=False)
    assert "dist/embed.js" in html
    assert "dist/embed-amd.js" not in html
    assert "require.min.js" not in html


def test_write_html_matches_embed_html(tmp_path) -> None:
    doc = _doc()
    out = tmp_path / "widgets.html"
    write_html(out, doc)
    assert out.read_text() == embed_html(doc)
