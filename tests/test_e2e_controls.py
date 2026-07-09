"""LIVE-KERNEL check for the real-controls catalog builder (cositos-70b.2 AC #3).

The rule-of-5 review flagged that a static-only check (embed_html against the CDN
html-manager) is not sufficient evidence that a builder-produced widget behaves as a real
``@jupyter-widgets/controls`` widget over an actual comm. This mirrors
``tests/test_e2e_jupyter.py``'s harness (subprocess ``ipykernel`` + ``jupyter_client``) but
opens a widget built by :func:`cositos.contrib.controls.int_slider` through
``cositos.model.Widget``/``cositos.jupyter.CommTransport``, and asserts the real
``comm_open`` on iopub carries the real controls identity (not anywidget's ``AnyModel``).

Skipped unless the e2e extras (ipykernel + jupyter_client) are installed.
"""

from __future__ import annotations

import contextlib
from queue import Empty

import pytest

jupyter_client = pytest.importorskip("jupyter_client")
ipykernel_ks = pytest.importorskip("ipykernel.kernelspec")

from jupyter_client.kernelspec import KernelSpecManager  # noqa: E402
from jupyter_client.manager import start_new_kernel  # noqa: E402

KERNEL_NAME = "cositos-e2e-controls"

SETUP_CODE = """
from cositos import Widget
from cositos.jupyter import CommTransport
from cositos.contrib.controls import int_slider

_entries = int_slider(value=7, min=0, max=100)
_root_id, _state = _entries[0]
_t = CommTransport()
_w = Widget(_t, get_state=lambda: dict(_state), set_state=_state.update, model_id=_root_id)
_w.open()
print("COMM_ID", _t.comm_id)
"""


@pytest.fixture(scope="module")
def kernelspec():
    ipykernel_ks.install(user=True, kernel_name=KERNEL_NAME)
    yield KERNEL_NAME
    with contextlib.suppress(Exception):
        KernelSpecManager().remove_kernel_spec(KERNEL_NAME)


@pytest.fixture
def kernel(kernelspec):
    km, kc = start_new_kernel(kernel_name=kernelspec)
    try:
        yield kc
    finally:
        kc.stop_channels()
        km.shutdown_kernel(now=True)


def _run(kc, code: str, timeout: float = 30.0) -> None:
    msg_id = kc.execute(code)
    while True:
        msg = kc.get_shell_msg(timeout=timeout)
        if msg["parent_header"].get("msg_id") == msg_id:
            assert msg["content"]["status"] == "ok", msg["content"]
            return


def _drain_iopub(kc, timeout: float = 3.0) -> list[dict]:
    msgs = []
    while True:
        try:
            msgs.append(kc.get_iopub_msg(timeout=timeout))
        except Empty:
            return msgs


def _by_type(msgs, msg_type):
    return [m for m in msgs if m["header"]["msg_type"] == msg_type]


@pytest.mark.e2e
def test_builder_produced_widget_opens_with_real_controls_identity_over_a_real_kernel(kernel):
    kc = kernel

    _run(kc, SETUP_CODE)
    msgs = _drain_iopub(kc)
    opens = _by_type(msgs, "comm_open")
    assert opens, "expected a comm_open message"
    state = opens[0]["content"]["data"]["state"]

    # The point of this test: NOT anywidget's AnyModel/AnyView (test_e2e_jupyter.py
    # already certifies that path) — the real @jupyter-widgets/controls identity,
    # live, over an actual comm_open, not just a statically exported document.
    assert state["_model_module"] == "@jupyter-widgets/controls"
    assert state["_model_name"] == "IntSliderModel"
    assert state["_view_module"] == "@jupyter-widgets/controls"
    assert state["_view_name"] == "IntSliderView"
    assert state["value"] == 7
    assert state["min"] == 0
    assert state["max"] == 100
    # Companion refs resolve to entries the SETUP_CODE would also have to open
    # separately in a live app; here we only assert the widget's own state is correct,
    # matching the wire-level check in the research note (Method #1).
    assert state["style"].startswith("IPY_MODEL_")
    assert state["layout"].startswith("IPY_MODEL_")
