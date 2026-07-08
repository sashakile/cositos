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
- **Julia** (`julia-1.12`): `julia -e 'using Pkg; Pkg.add("IJulia")'` then
  `julia -e 'using IJulia; IJulia.installkernel("Julia")'`. IJulia comes from the General
  registry (not a GitHub release asset), so it is **not** proxy-blocked. `installkernel`
  writes the kernelspec under `JUPYTER_DATA_DIR`. The kernel name is version-stamped
  (`julia-1.12`), so invoke the probe with an explicit program key: `--program julia`.
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
| `ir` (IRkernel) | ✅ | *blocked* | comm API exists (`IRkernel:::Comm`), but kernel-initiated `comm$open()` throws an internal `send_response` arity error in IRkernel **1.3.2** (latest CRAN) — widgets need the kernel to open a comm, so R is blocked upstream. Probe program (`ir`) kept to re-test once IRkernel fixes it. |
| `.net-csharp` (.NET Interactive) | ✅ | *blocked* | does **not** answer `comm_info_request` — .NET Interactive uses its own bespoke kernel protocol, not the standard ipywidgets comm surface cositos targets. Not usable without a comm shim. |
| `cositos-clj` (clojupyter) | ✅ | **1** (crack) | **answers `comm_info_request`** and, per the confirmed spike below, reaches **Tier 1 (BIDIRECTIONAL)** via the `current-context` crack — `mise run probe -- cositos-clj --program clojure`. Not a public/upstream API: reaches into an internal, version-coupled namespace (`clojupyter.state/current-context`). The clojupyter-native widget-layer gap (no `widget` ns, private emit fns) is unchanged; see "clojupyter comm surface" below. |
| `julia-1.12` (IJulia) | ✅ | **1** | full two-way comm via `IJulia.CommManager.Comm` (mutable `on_msg` field + `send_comm`). Kernel-initiated `comm_open` works and frontend→kernel `comm_msg` is echoed back — same round trip as `python3`. Probe program key: `julia` (run `mise run probe -- julia-1.12 --program julia`). Unblocks the Julia notebook (`cositos-059.2`) and IJulia transport adapter (`cositos-z76.6`). |

Kernels are installed and launch; **`python3`, `julia-1.12`, and `cositos-clj` (via the
current-context crack) support the full widget-comm round trip**. `ir` and `.net-csharp`
remain blocked upstream for distinct reasons (IRkernel bug; .NET Interactive's non-standard
protocol) — see the table.
This is the core finding of the batch: the protocol *cores* port trivially and are all
fixture-certified, but the *kernel comm ecosystem* is the real barrier. Classifying each
kernel is the first step of the transport tickets `cositos-ex2.5/6/7`.

## Clojure without a kernel: Clay (the recommended host)

clojupyter's *native* comm layer still ships no user-facing comm-open API and no widget
namespace (the `current-context` crack above reaches Tier 1 only by climbing into internal,
version-coupled implementation details — see the caveat in "clojupyter comm surface").
Widgets don't strictly need a Jupyter kernel, though — they need a bidirectional channel.
**Clay**
(`org.scicloj/clay`, Scicloj's REPL-driven notebook/visualization tool) is *not* a kernel
and has no comm protocol, yet it exposes a **full-duplex public websocket** (JVM→browser
via `broadcast!`/`scittle-eval-string!`; browser→JVM via `install-websocket-handler!
:on-receive`). That is a strictly *public* API — no kernel internals, no upstream patch —
unlike clojupyter's private emit fns.

Verified live (spike `cositos-059.7`, transport+demo `cositos-059.8`): a real browser
exchanges cositos widget messages with the JVM over Clay's websocket, and the actual
`@cositos/front` `Model` + `ClayChannel` drive a JVM-authoritative counter end-to-end.
Wire format: a `cositos <json>` text frame (`{msg, buffers}`) with binary buffers
base64-inline, since Clay frames are text. Reproduce with `clojure -M:clay-demo` in
`clojure/` then open `http://localhost:1971/`. So the recommended route to interactive
cositos widgets in Clojure is **Clay, not clojupyter**.

## clojupyter comm surface (jar introspection, 0.4.332)

Why clojupyter is classified "no user-facing comm-open API", from introspecting the
installed `clojupyter-0.4.332.jar` (AOT-compiled; class names + a live `ns-resolve` of the
function metadata):

- **Comm plumbing exists, no widget layer.** The jar has `clojupyter.messages` (builders
  `comm-open-content`, `comm-msg-content`, `comm-close-content`), `clojupyter.kernel.comm-atom`,
  `clojupyter.kernel.comm-global-state`, and an inbound `clojupyter.kernel.handle-event/handle-comm`.
  There is **no `widget` namespace anywhere** — comms are a primitive, with no ipywidgets layer on top.
- **The emit functions are private.** `clojupyter.kernel.comm-atom/send-comm-open!` and
  `send-comm-msg!` — the functions that actually put a `comm_open`/`comm_msg` on the wire —
  are both `:private true` (verified via `(:private (meta (ns-resolve ...)))`). Not public API.
- **The public constructors need kernel internals.** The public entry points
  `create` / `create-and-insert` have arglist `[jup req-message target-name comm-id comm-state]`.
  `jup` is the live ZMQ channel object and `req-message` is the in-flight request (for parent-
  header routing); **neither is available to ordinary notebook-cell code** — they exist only
  inside clojupyter's own message-handling loop.

So a user cell cannot open a comm: the emit fns are private *and* the constructor args are
kernel internals. This is an **upstream API-surface gap, not a crash** (contrast R).

**In-process crack — CONFIRMED live (`cositos-059.9`):** `clojupyter.state/current-context`
(+ `with-current-context`/`push-context!`) does carry `:jup` + `:req-message` while a cell is
executing — verified by evaluating `(state/current-context)` inside a running `cositos-clj`
kernel:

```
{:cljsrv #NREPL[...], :jup #Jup, :term #Terminator,
 :req-message {:header {...}, :content {...}, ...}, :req-port :shell_port}
```

Chaining `current-context → create-and-insert (public)` opens a real comm — `create-and-insert`
is public and calls the private `send-comm-open!` internally, so no `var-get`/private-fn access
is even needed. A `comm_open` message was observed on the wire from ordinary cell code, with
no clojupyter source patch:

```clojure
(require '[clojupyter.state :as state])
(require '[clojupyter.kernel.comm-atom :as comm-atom])
(let [ctx (state/current-context)
      jup (:jup ctx)
      req (:req-message ctx)
      comm-id (str (java.util.UUID/randomUUID))
      ca (comm-atom/create-and-insert jup req "cositos.probe" comm-id {:hello 1})]
  (comm-atom/watch ca :probe-echo
    (fn [_ _ _ new-state]
      (when-not (:echo new-state)
        (comm-atom/state-update! ca {:echo true})))))
```

The round trip is full **Tier 1 (BIDIRECTIONAL)**: `comm-atom/state-update!` (public) broadcasts
kernel→frontend, and `comm-atom/watch` (public, add-watch-style) fires on frontend→kernel
inbound state changes — confirmed by sending a `comm_msg` and observing the watch-triggered
echo on the wire. Reproduce with `mise run probe -- cositos-clj --program clojure` (added to
`probe/kernel_probe.py`'s `PROBE_PROGRAMS`).

**Protocol quirk found along the way:** clojupyter's inbound `comm_msg` dispatch is a
multimethod keyed on a required `:method` field (the ipywidgets-protocol shape, e.g.
`{"method": "update", "state": {...}}`). A generic raw payload (no `:method`, as ipykernel
accepts) throws `Assert failed: method` inside clojupyter's async dispatch thread — uncaught,
and invisible to the client (no shell reply, no iopub error). `kernel_probe.py` accounts for
this via a per-program `PROBE_PING_PAYLOAD` override.

**Caveat — this is not an upstream-sanctioned API.** The crack reaches into
`clojupyter.state/current-context`, an internal, version-coupled implementation detail (not
documented, not part of clojupyter's public API, and free to change/disappear in a future
clojupyter release without notice). It is a viable *implementation path* for a Transport
adapter, not a substitute for clojupyter shipping a public comm-open API.
