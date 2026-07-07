"""Static-export mechanism: a cositos widget embeds into nbconvert HTML with no kernel.

Opt-in: skipped unless nbconvert/nbformat are installed (the `export` extra). This is the
shared foundation for JupyterBook (nbconvert) and Quarto (same `metadata.widgets` block).
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("nbconvert")
pytest.importorskip("nbformat")

_BUILD = Path(__file__).resolve().parent.parent / "examples" / "static-export" / "build.py"


def _build_module():
    spec = importlib.util.spec_from_file_location("cositos_static_build", _BUILD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_widget_embeds_into_static_html_without_a_kernel():
    build = _build_module()
    entries = [("counter", {"_esm": build.COUNTER_ESM, "n": 3})]
    html = build.build_html(entries, ["counter"])

    # The notebook-level widget-state Document is embedded...
    state_block = re.search(
        r'<script type="' + re.escape(build.STATE_MIMETYPE) + r'">\s*(\{.*?\})\s*</script>',
        html,
        re.DOTALL,
    )
    assert state_block is not None
    doc = json.loads(state_block.group(1))
    assert set(doc["state"]) == {"counter"}
    assert doc["state"]["counter"]["state"]["n"] == 3

    # ...carrying the anywidget view identity so the html-manager can render it
    # (cositos-mx7 regression / cositos-d33 gap): structural presence is not enough.
    counter_state = doc["state"]["counter"]["state"]
    assert counter_state["_view_name"] == "AnyView"
    assert counter_state["_view_module"] == "anywidget"
    assert "_view_module_version" in counter_state
    assert "_view_count" in counter_state

    # ...and the cell's widget-view output references the model.
    assert build.VIEW_MIMETYPE in html
    assert "counter" in html
