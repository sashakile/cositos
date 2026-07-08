"""True end-to-end test against a REAL clojupyter kernel.

The Clojure analogue of ``tests/test_e2e_julia.py``. Launches a clojupyter kernel via
``jupyter_client``, and inside it: uses ``pomegranate`` (bundled in clojupyter) to add this
repo's ``clojure/src`` and ``clojure/dev`` to the kernel's classpath at runtime, then opens
a widget over the real ``cositos.clojupyter-transport`` (the current-context crack
confirmed live in cositos-059.9). Asserts the actual iopub comm traffic (``comm_open``, a
kernel->frontend ``update``, and a frontend->kernel ``update``) matches the widget
messaging protocol — the "does it really work in a clojupyter kernel?" check that backs
cositos-ex2.5.

Skipped unless ``clojure`` is on PATH and the e2e extras (jupyter_client) are installed.
Installs a throwaway kernelspec pointing at a bare ``clojupyter/clojupyter`` deps map (no
cositos on its classpath — that's added at runtime via pomegranate, exactly as a real
user's notebook would do; see ``clojure/dev/cositos/clojupyter_transport.clj`` for why this
can't simply be a `-Sdeps :paths` entry: clojupyter is the kernel process itself).
"""

from __future__ import annotations

import contextlib
import json
import shutil
from pathlib import Path
from queue import Empty

import pytest

jupyter_client = pytest.importorskip("jupyter_client")

if shutil.which("clojure") is None:  # pragma: no cover - environment guard
    pytest.skip("clojure not on PATH", allow_module_level=True)

from jupyter_client.kernelspec import KernelSpecManager  # noqa: E402
from jupyter_client.manager import start_new_kernel  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
KERNEL_NAME = "cositos-clojure-e2e"

# Bare clojupyter kernel (no cositos on its classpath) -- the setup code below adds this
# repo's clojure/src + clojure/dev to the classpath at runtime via pomegranate, exactly as
# a real notebook would.
KERNEL_JSON = {
    "argv": [
        "clojure",
        "-Sdeps",
        '{:deps {clojupyter/clojupyter {:mvn/version "0.4.332"}} '
        ':mvn/repos {"clojars" {:url "https://repo.clojars.org/"}}}',
        "-M",
        "-m",
        "clojupyter.kernel.core",
        "{connection_file}",
    ],
    "display_name": "Clojure (cositos e2e)",
    "language": "clojure",
}

SETUP_CODE = f"""
(require '[cemerick.pomegranate :as pom])
(pom/add-classpath "{REPO_ROOT}/clojure/src")
(pom/add-classpath "{REPO_ROOT}/clojure/dev")
(require '[cositos.clojupyter-transport :as tx])

(def _store (atom {{"_esm" "export default {{ render({{model, el}}) {{}} }}" "value" 0}}))
(def _transport (tx/open! @_store))
(tx/on-update! _transport (fn [new-state] (reset! _store new-state)))
"""


@pytest.fixture(scope="module")
def kernelspec():
    ksm = KernelSpecManager()
    with contextlib.suppress(Exception):
        ksm.remove_kernel_spec(KERNEL_NAME)
    tmp_dir = Path(ksm.user_kernel_dir) / KERNEL_NAME
    tmp_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "kernel.json").write_text(json.dumps(KERNEL_JSON))
    yield KERNEL_NAME
    with contextlib.suppress(Exception):
        ksm.remove_kernel_spec(KERNEL_NAME)


@pytest.fixture
def kernel(kernelspec):
    km, kc = start_new_kernel(kernel_name=kernelspec, startup_timeout=120)
    try:
        yield kc
    finally:
        kc.stop_channels()
        km.shutdown_kernel(now=True)


def _run(kc, code: str, timeout: float = 60.0) -> None:
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
def test_end_to_end_comm_lifecycle_over_real_clojupyter_kernel(kernel):
    kc = kernel

    # 1. Opening the transport (the current-context crack) emits a spec-correct comm_open.
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
    comm_id = open_content["comm_id"]

    # 2. Kernel -> frontend: send-state! emits an `update` comm_msg, string-keyed.
    _run(kc, '(tx/send-state! _transport {"value" 42})')
    updates = [
        m
        for m in _by_type(_drain_iopub(kc), "comm_msg")
        if m["content"]["data"].get("method") == "update"
    ]
    assert updates, "expected an update comm_msg"
    assert updates[-1]["content"]["data"]["state"]["value"] == 42

    # 3. Frontend -> kernel: an inbound `update` reaches on-update!'s handler (via
    # clojupyter's own comm-atom merge), not just the wire -- and with STRING keys, not
    # clojupyter's internal keyword-keyed representation (the key-representation caveat
    # in cositos.clojupyter-transport's docstring).
    req = kc.session.msg(
        "comm_msg", {"comm_id": comm_id, "data": {"method": "update", "state": {"value": 7}}}
    )
    kc.shell_channel.send(req)
    _drain_iopub(kc)  # let clojupyter's own merge + our watch settle
    _run(kc, '(println (get @_store "value"))')
    out = _by_type(_drain_iopub(kc), "stream")
    assert out and out[-1]["content"]["text"].strip() == "7", (
        f"on-update! should have merged the inbound value with STRING keys: {out}"
    )
