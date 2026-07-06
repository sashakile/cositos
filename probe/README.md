# Kernel capability probe

Widgets require the Jupyter **comm** protocol — a bidirectional message channel between the
kernel and the frontend. Not every Jupyter kernel implements it fully, and *that* (not the
language) decides whether cositos widgets can work there. This probe answers, empirically,
"can kernel X carry widgets?" before we invest in a `Transport` adapter for it.

## Tiers

| Tier | Meaning | Widget experience |
|------|---------|-------------------|
| **1 BIDIRECTIONAL** | `comm_open` observed **and** a frontend→kernel message is echoed back | full two-way widgets |
| **2 BROADCAST_ONLY** | `comm_open` observed, but no reply routing | one-way widgets (`supports_receive=false`) |
| **3 NO_COMM** | no `comm_open` at all | widgets impossible without a kernel patch |

## Usage

```bash
mise run probe -- python3          # or:  uv run --extra e2e python probe/kernel_probe.py python3
# python3: Tier 1 (BIDIRECTIONAL)
```

`<kernel>` is an installed kernel name (`jupyter kernelspec list`). If the kernel's name
differs from its probe-program key, reuse a program explicitly:

```bash
mise run probe -- my-python-kernel --program python3
```

## How it works

`kernel_probe.py` launches the kernel via `jupyter_client`, executes a small **probe
program** written in the kernel's own language, and then classifies the kernel purely from
the wire-level comm messages it observes (the classifier is language-agnostic). The probe
program must:

1. open a comm to target `cositos.probe` and send one message, and
2. register a handler that echoes any inbound `comm_msg` back as a new `comm_msg`.

## Adding a kernel

Add an entry to `PROBE_PROGRAMS` in `kernel_probe.py`, keyed by the kernel name, whose value
is the probe program in that kernel's language. For example, the `python3` program uses
`ipykernel.comm.Comm`. An R entry would use IRkernel's comm API, a C# entry .NET
Interactive's, and so on — the same comm surface the eventual `Transport` adapter builds on.

## Known results

| Kernel | Tier | Notes |
|--------|------|-------|
| `python3` (ipykernel) | **1** | certified by `tests/test_kernel_probe.py` |
| R (IRkernel) | *unverified* | kernel not yet installed |
| C# (.NET Interactive) | *unverified* | kernel not yet installed; highest-uncertainty |
| Clojure (clojupyter) | *unverified* | kernel not yet installed; may be Tier 3 |

Verifying the batch-1 kernels is the first step of each transport ticket
(`cositos-ex2.5/6/7`), which this probe gates.
