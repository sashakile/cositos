"""Kernel capability probe: classify a Jupyter kernel's widget-comm support.

Widgets require the Jupyter *comm* protocol. Kernels vary in how much of it they implement,
which — not the language — decides whether cositos widgets can work there. This probe
launches a kernel, runs a tiny language-specific *probe program* that opens a comm and
echoes inbound messages, and classifies the kernel from the comm traffic it observes:

  Tier 1  BIDIRECTIONAL   comm_open seen AND a frontend->kernel message is echoed back
  Tier 2  BROADCAST_ONLY  comm_open seen but no reply routing (one-way widgets only)
  Tier 3  NO_COMM         no comm_open at all (widgets impossible without a kernel patch)

Adding a kernel = add its probe program to PROBE_PROGRAMS (see README.md). The classifier
itself is language-agnostic — it only reads the wire-level comm messages.

CLI:  python probe/kernel_probe.py <kernel-name> [--program <key>]
Requires jupyter_client (the e2e extra).
"""

from __future__ import annotations

import argparse
import enum
import sys
from queue import Empty

PROBE_TARGET = "cositos.probe"


class Tier(enum.IntEnum):
    BIDIRECTIONAL = 1
    BROADCAST_ONLY = 2
    NO_COMM = 3

    @property
    def label(self) -> str:
        return {1: "BIDIRECTIONAL", 2: "BROADCAST_ONLY", 3: "NO_COMM"}[int(self)]


class ProbeError(RuntimeError):
    """The probe program failed to run (e.g. wrong language for the kernel)."""


# Per-kernel-language probe programs. Each must: open a comm to PROBE_TARGET, send one
# message, and register a handler that echoes any inbound comm_msg back as a new comm_msg.
PROBE_PROGRAMS: dict[str, str] = {
    "python3": (
        "from ipykernel.comm import Comm\n"
        '_probe_comm = Comm(target_name="cositos.probe", data={"hello": 1})\n'
        "def _probe_on(msg):\n"
        '    _probe_comm.send({"echo": True})\n'
        "_probe_comm.on_msg(_probe_on)\n"
    ),
    "ir": (
        'comm <- IRkernel:::Comm(target_name = "cositos.probe", id = "cositos-probe-1")\n'
        "comm$on_msg(function(msg) comm$send(list(echo = TRUE)))\n"
        "comm$open(msg = list(hello = 1))\n"
    ),
    "julia": (
        "import IJulia.CommManager\n"
        '_probe_comm = CommManager.Comm("cositos.probe"; data=Dict("hello"=>1))\n'
        '_probe_comm.on_msg = (msg) -> CommManager.send_comm(_probe_comm, Dict("echo"=>true))\n'
    ),
    # clojupyter has no public comm-open API (see probe/README.md "clojupyter comm surface").
    # This program exploits the `clojupyter.state/current-context` crack, confirmed live in
    # cositos-059.9: during cell execution, current-context carries :jup + :req-message, which
    # the *public* `create-and-insert` accepts directly -- no private-fn access needed, and no
    # clojupyter source patch. `watch` mirrors on_msg: it fires on every inbound state change
    # (including the kernel's own auto-applied "update", so the echo-state guard is required to
    # avoid an infinite feedback loop across two clojupyter watch cycles).
    "clojure": (
        "(require '[clojupyter.state :as state])\n"
        "(require '[clojupyter.kernel.comm-atom :as comm-atom])\n"
        "(let [ctx (state/current-context)\n"
        "      jup (:jup ctx)\n"
        "      req (:req-message ctx)\n"
        "      comm-id (str (java.util.UUID/randomUUID))\n"
        '      ca (comm-atom/create-and-insert jup req "cositos.probe" comm-id {:hello 1})]\n'
        "  (comm-atom/watch ca :probe-echo\n"
        "    (fn [_ _ _ new-state]\n"
        "      (when-not (:echo new-state)\n"
        "        (comm-atom/state-update! ca {:echo true})))))\n"
    ),
}

# Per-program override for the frontend->kernel ping payload (default: {"ping": 1}).
# clojupyter's inbound comm_msg dispatch is a multimethod keyed on a required :method field
# (ipywidgets-protocol shape); a payload without :method throws `Assert failed: method` inside
# clojupyter's async dispatch thread -- uncaught, and invisible to the client (no shell/iopub
# error), so a generic {"ping": 1} probe against clojupyter silently looks like BROADCAST_ONLY.
PROBE_PING_PAYLOAD: dict[str, dict] = {
    "clojure": {"method": "update", "state": {"ping": 1}},
}
DEFAULT_PING_PAYLOAD: dict = {"ping": 1}


def _execute(kc, code: str, timeout: float) -> None:
    msg_id = kc.execute(code)
    while True:
        msg = kc.get_shell_msg(timeout=timeout)
        if msg["parent_header"].get("msg_id") == msg_id:
            status = msg["content"]["status"]
            if status != "ok":
                raise ProbeError(f"probe program failed on this kernel: {msg['content']}")
            return


def _drain_iopub(kc, timeout: float) -> list[dict]:
    msgs: list[dict] = []
    while True:
        try:
            msgs.append(kc.get_iopub_msg(timeout=timeout))
        except Empty:
            return msgs


def _of_type(msgs, msg_type):
    return [m for m in msgs if m["header"]["msg_type"] == msg_type]


def probe(kernel_name: str, program: str | None = None, timeout: float = 15.0) -> Tier:
    """Launch `kernel_name`, run its probe program, and return the observed capability Tier."""
    from jupyter_client.manager import start_new_kernel

    key = program or kernel_name
    if key not in PROBE_PROGRAMS:
        raise ProbeError(
            f"no probe program for {key!r}; known: {sorted(PROBE_PROGRAMS)} "
            f"(pass --program to reuse one)"
        )
    source = PROBE_PROGRAMS[key]

    km, kc = start_new_kernel(kernel_name=kernel_name)
    try:
        _execute(kc, source, timeout)
        opens = _of_type(_drain_iopub(kc, timeout=3.0), "comm_open")
        if not opens:
            return Tier.NO_COMM
        comm_id = opens[0]["content"]["comm_id"]

        # Frontend -> kernel: send a comm_msg and see whether the kernel echoes it back.
        payload = PROBE_PING_PAYLOAD.get(key, DEFAULT_PING_PAYLOAD)
        req = kc.session.msg("comm_msg", {"comm_id": comm_id, "data": payload})
        kc.shell_channel.send(req)
        echoed = _of_type(_drain_iopub(kc, timeout=3.0), "comm_msg")
        return Tier.BIDIRECTIONAL if echoed else Tier.BROADCAST_ONLY
    finally:
        kc.stop_channels()
        km.shutdown_kernel(now=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify a Jupyter kernel's widget-comm support.")
    parser.add_argument("kernel", help="installed kernel name (see `jupyter kernelspec list`)")
    parser.add_argument("--program", help="probe-program key to run (default: the kernel name)")
    args = parser.parse_args(argv)
    try:
        tier = probe(args.kernel, program=args.program)
    except ProbeError as exc:
        print(f"probe error: {exc}", file=sys.stderr)
        return 2
    print(f"{args.kernel}: Tier {int(tier)} ({tier.label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
