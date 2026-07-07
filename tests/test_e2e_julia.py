"""True end-to-end test against a REAL IJulia (Julia Jupyter) kernel.

The Julia analogue of ``tests/test_e2e_jupyter.py``. Launches an IJulia kernel via
``jupyter_client``, creates a cositos ``Widget`` inside it over the real ``IJuliaCommTransport``
(from the ``CositosIJuliaExt`` package extension), and asserts the actual iopub comm
traffic — ``comm_open``, an ``update``, and a ``request_state`` round-trip — matches the
widget messaging protocol. This is the "does it really work in a Julia kernel?" check that
backs the Tier-1 finding from ``probe/README.md``.

Skipped unless ``julia`` is on PATH and the e2e extras (jupyter_client) are installed. The
fixture builds a throwaway Julia project that ``dev``s the local ``julia/`` package and adds
IJulia, then installs a kernelspec bound to it (first run precompiles — allow time).
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from pathlib import Path
from queue import Empty

import pytest

jupyter_client = pytest.importorskip("jupyter_client")

if shutil.which("julia") is None:  # pragma: no cover - environment guard
    pytest.skip("julia not on PATH", allow_module_level=True)

from jupyter_client.kernelspec import KernelSpecManager  # noqa: E402
from jupyter_client.manager import start_new_kernel  # noqa: E402

JULIA_DIR = Path(__file__).resolve().parent.parent / "julia"

# Julia setup run inside the kernel: build a widget over the IJulia comm transport.
SETUP_CODE = r"""
using Cositos, IJulia
_store = Dict{String,Any}("_esm" => "export default { render({model, el}) {} }", "value" => 0)
_t = Cositos.ijulia_transport()
_w = Widget(_t; get_state = () -> copy(_store), set_state = (d) -> merge!(_store, d))
open!(_w)
"""


@pytest.fixture(scope="module")
def julia_kernel_name(tmp_path_factory):
    proj = tmp_path_factory.mktemp("cositos_julia_e2e")
    install = (
        f'import Pkg; Pkg.activate(raw"{proj}"); '
        f'Pkg.develop(path=raw"{JULIA_DIR}"); Pkg.add("IJulia"); '
        f"using IJulia; "
        f'p = IJulia.installkernel("cositos-julia-e2e"; env=Dict("JULIA_PROJECT"=>raw"{proj}")); '
        f"println(basename(p))"
    )
    result = subprocess.run(
        ["julia", "-e", install], capture_output=True, text=True, timeout=600, check=False
    )
    if result.returncode != 0:  # pragma: no cover - surfaces setup failures clearly
        pytest.fail(f"julia kernel setup failed:\n{result.stdout}\n{result.stderr}")
    name = result.stdout.strip().splitlines()[-1]
    yield name
    with contextlib.suppress(Exception):  # best-effort cleanup
        KernelSpecManager().remove_kernel_spec(name)


@pytest.fixture
def kernel(julia_kernel_name):
    km, kc = start_new_kernel(kernel_name=julia_kernel_name)
    try:
        yield kc
    finally:
        kc.stop_channels()
        km.shutdown_kernel(now=True)


def _run(kc, code: str, timeout: float = 120.0) -> None:
    msg_id = kc.execute(code)
    while True:
        msg = kc.get_shell_msg(timeout=timeout)
        if msg["parent_header"].get("msg_id") == msg_id:
            assert msg["content"]["status"] == "ok", msg["content"]
            return


def _drain_iopub(kc, timeout: float = 5.0) -> list[dict]:
    msgs = []
    while True:
        try:
            msgs.append(kc.get_iopub_msg(timeout=timeout))
        except Empty:
            return msgs


def _by_type(msgs, msg_type):
    return [m for m in msgs if m["header"]["msg_type"] == msg_type]


@pytest.mark.e2e
def test_end_to_end_comm_lifecycle_over_real_ijulia_kernel(kernel):
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

    # 2. Mutating state + send_state!() emits an `update` comm_msg.
    _run(kc, '_store["value"] = 42; send_state!(_w)')
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


@pytest.mark.e2e
def test_display_emits_widget_view_mimebundle(kernel):
    # A fresh widget displayed on a cell's last line must auto-open its comm and emit the
    # anywidget widget-view mimetype as a JSON object (model_id matching the opened comm),
    # so it renders live — the Julia analogue of Python's Widget._repr_mimebundle_.
    kc = kernel
    setup = (
        "using Cositos, IJulia\n"
        '_s2 = Dict{String,Any}("_esm" => "export default { render() {} }", "count" => 0)\n'
        "_w2 = Widget(Cositos.ijulia_transport(); get_state = () -> copy(_s2))\n"
        "display(_w2)\n"
    )
    _run(kc, setup)
    msgs = _drain_iopub(kc)

    mime = "application/vnd.jupyter.widget-view+json"
    displays = [m for m in _by_type(msgs, "display_data") if mime in m["content"]["data"]]
    assert displays, "expected a display_data carrying the widget-view mimetype"
    view = displays[-1]["content"]["data"][mime]
    assert view["version_major"] == 2
    assert view["version_minor"] == 1

    # The displayed model_id must match the comm the display auto-opened.
    opens = _by_type(msgs, "comm_open")
    assert opens, "display must auto-open the comm"
    assert view["model_id"] == opens[-1]["content"]["comm_id"]
