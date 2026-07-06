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

## Installing the batch-1 kernels (hard-won recipes)

All four language kernels are installed and verified to launch. Kernelspecs live in
`~/Library/Jupyter/kernels` (set `JUPYTER_DATA_DIR=~/Library/Jupyter` during install so the
venv's `jupyter_client` discovers them).

- **Python** (`python3`): ships with the venv (ipykernel).
- **R** (`ir`): `Rscript -e 'install.packages("IRkernel"); IRkernel::installspec(name="ir")'`
  from CRAN. `installspec` shells out to `jupyter`, so run it with the venv's `jupyter` on
  PATH (e.g. under `uv run`).
- **C#** (`.net-csharp`): `dotnet tool install --global Microsoft.dotnet-interactive` then
  `dotnet interactive jupyter install`. Its generated `kernel.json` calls bare `dotnet
  interactive` with no env — patch it to use an absolute `dotnet` path and add an `env`
  block with `DOTNET_ROOT` and a `PATH` that includes `~/.dotnet/tools`, or the kernel dies
  before the `kernel_info` handshake.
- **Clojure** (`cositos-clj`): clojupyter's normal install needs a prebuilt standalone jar,
  distributed as a **GitHub release asset — blocked by the proxy here**. Work around it with
  a **jar-free deps-based kernelspec** that launches clojupyter's kernel entry point straight
  from Clojars:

  ```json
  {
    "argv": ["/opt/homebrew/bin/clojure", "-Sdeps",
      "{:deps {clojupyter/clojupyter {:mvn/version \"0.4.332\"}} :mvn/repos {\"clojars\" {:url \"https://repo.clojars.org/\"}}}",
      "-M", "-m", "clojupyter.kernel.core", "{connection_file}"],
    "display_name": "Clojure (cositos)", "language": "clojure"
  }
  ```

## Known results

| Kernel | Installed / launches | Tier | Notes |
|--------|----------------------|------|-------|
| `python3` (ipykernel) | ✅ | **1** | certified by `tests/test_kernel_probe.py` |
| `ir` (IRkernel) | ✅ | *unverified* | needs an R probe program (IRkernel comm API) |
| `.net-csharp` (.NET Interactive) | ✅ | *unverified* | needs a C# probe program; comm mapping is the least certain |
| `cositos-clj` (clojupyter) | ✅ | *unverified* | clojupyter ships comm *message specs* but no user-facing comm API — likely Tier 3 |

Kernels are installed and launch; their **tiers are still unverified** — classifying each
requires writing its probe program (the seed of that language's `Transport`), which is the
first step of the transport tickets `cositos-ex2.5/6/7`.
