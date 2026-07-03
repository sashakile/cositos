"""True end-to-end test against a REAL Jupyter kernel.

Launches an ipykernel subprocess via jupyter_client, creates a cositos widget inside it
(using the real `comm` machinery through `CommTransport`), and asserts the actual iopub
comm traffic — `comm_open`, `update`, and a `request_state` round-trip — matches the
widget messaging protocol. This is the "does it really work in Jupyter?" check.

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

KERNEL_NAME = "cositos-e2e"

SETUP_CODE = """
from cositos import Widget
from cositos.jupyter import CommTransport

_store = {"_esm": "export default { render({model, el}) {} }", "value": 0}
_t = CommTransport()
_w = Widget(_t, get_state=lambda: dict(_store), set_state=_store.update)
_w.open()
print("COMM_ID", _t.comm_id)
"""


@pytest.fixture(scope="module")
def kernelspec():
    # Install a kernelspec that launches with THIS interpreter (so cositos is importable).
    ipykernel_ks.install(user=True, kernel_name=KERNEL_NAME)
    yield KERNEL_NAME
    with contextlib.suppress(Exception):  # best-effort cleanup
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
def test_end_to_end_comm_lifecycle_over_real_kernel(kernel):
    kc = kernel

    # 1. Creating the widget emits a spec-correct comm_open on iopub.
    _run(kc, SETUP_CODE)
    msgs = _drain_iopub(kc)
    opens = _by_type(msgs, "comm_open")
    assert opens, "expected a comm_open message"
    open_content = opens[0]["content"]
    assert open_content["target_name"] == "jupyter.widget"
    state = open_content["data"]["state"]
    assert state["_model_module"] == "anywidget"
    assert state["_model_name"] == "AnyModel"
    assert state["_view_name"] == "AnyView"
    assert state["value"] == 0
    assert opens[0]["metadata"]["version"] == "2.1.0"
    comm_id = open_content["comm_id"]

    # 2. Mutating state + send_state() emits an `update` comm_msg.
    _run(kc, '_store["value"] = 42; _w.send_state()')
    update_msgs = _by_type(_drain_iopub(kc), "comm_msg")
    updates = [m for m in update_msgs if m["content"]["data"].get("method") == "update"]
    assert updates, "expected an update comm_msg"
    assert updates[-1]["content"]["data"]["state"]["value"] == 42

    # 3. Frontend -> kernel: send a `request_state` comm_msg; kernel replies with update.
    req = kc.session.msg("comm_msg", {"comm_id": comm_id, "data": {"method": "request_state"}})
    kc.shell_channel.send(req)
    replies = _by_type(_drain_iopub(kc), "comm_msg")
    state_replies = [m for m in replies if m["content"]["data"].get("method") == "update"]
    assert state_replies, "kernel should answer request_state with an update"
    assert state_replies[-1]["content"]["data"]["state"]["value"] == 42
