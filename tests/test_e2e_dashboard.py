"""LIVE-KERNEL check for the dashboard example (cositos-70b.4).

Mirrors tests/test_e2e_controls.py's harness (subprocess ipykernel + jupyter_client) but
proves the actual acceptance gate: sending a real inbound `update` comm_msg to the
slider's comm reaches the summary widget's comm_open ONLY through the shared host
Model — never by the dropdown's comm receiving anything, and never via
`ipywidgets.link`/`jslink`/peer `.observe()` (there is no ipywidgets kernel-side object
at all in this path; it's the same `cositos.contrib.controls` + `Dashboard` MVU wiring
`tests/test_example_dashboard.py` certifies against a fake transport, exercised here
against a REAL comm channel and a real subprocess kernel).

Skipped unless the e2e extras (ipykernel + jupyter_client) are installed.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from queue import Empty

import pytest

jupyter_client = pytest.importorskip("jupyter_client")
ipykernel_ks = pytest.importorskip("ipykernel.kernelspec")

from jupyter_client.kernelspec import KernelSpecManager  # noqa: E402
from jupyter_client.manager import start_new_kernel  # noqa: E402

KERNEL_NAME = "cositos-e2e-dashboard"

_BUILD_PATH = Path(__file__).resolve().parent.parent / "examples" / "dashboard" / "build.py"

SETUP_CODE = f"""
import importlib.util
from cositos.jupyter import CommTransport

spec = importlib.util.spec_from_file_location("cositos_dashboard_build", {str(_BUILD_PATH)!r})
_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_build)

_dash = _build.Dashboard(options=["low", "medium", "high"], value=25, index=0)
_slider_t = CommTransport()
_dropdown_t = CommTransport()
_summary_t = CommTransport()
_companion_entries = _dash._slider_entries[1:] + _dash._dropdown_entries[1:]
_companion_ts = [CommTransport() for _ in _companion_entries]
_dash.wire(_slider_t, _dropdown_t, _summary_t, companion_transports=_companion_ts)
print("IDS", _slider_t.comm_id, _dropdown_t.comm_id, _summary_t.comm_id)
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
def test_slider_update_reaches_the_summary_only_over_a_real_kernel(kernel):
    kc = kernel

    _run(kc, SETUP_CODE)
    opens = _by_type(_drain_iopub(kc), "comm_open")
    assert len(opens) == 7, "expected 3 interactive + 4 companion comm_opens"
    slider_comm_id, dropdown_comm_id, summary_comm_id = (o["content"]["comm_id"] for o in opens[:3])

    # Send a real inbound update comm_msg to the SLIDER's comm — exactly what a browser
    # drag would produce.
    req = kc.session.msg(
        "comm_msg",
        {"comm_id": slider_comm_id, "data": {"method": "update", "state": {"value": 77}}},
    )
    kc.shell_channel.send(req)
    _run(kc, "pass")  # a shell round-trip to make sure the kernel processed the comm_msg

    updates = _by_type(_drain_iopub(kc), "comm_msg")
    update_msgs = [m for m in updates if m["content"]["data"].get("method") == "update"]

    # The summary comm got exactly one update, with the recomputed text...
    summary_updates = [m for m in update_msgs if m["content"]["comm_id"] == summary_comm_id]
    assert len(summary_updates) == 1
    assert summary_updates[0]["content"]["data"]["state"]["text"] == "value=77, selection=low"

    # ...and the dropdown's comm received NOTHING (no peer link/observe fan-out).
    dropdown_updates = [m for m in update_msgs if m["content"]["comm_id"] == dropdown_comm_id]
    assert dropdown_updates == []
