# Research: Integrating cositos widgets with Clojure Clay

## Question
clojupyter is blocked as a widget host (probe classifies `cositos-clj` as *no
user-facing comm-open API* — see `probe/README.md`). Can we instead host cositos
widgets in **Clay**, the Scicloj REPL-driven notebook/visualization tool? What would
the integration look like, and is the bidirectional widget round-trip actually
achievable?

## Answer in one line
**Yes — Clay is a *better* host than clojupyter, now verified live.** Clay is not a
Jupyter kernel and does not use the comm protocol at all; it has its own **full-duplex
public transport** (a websocket in both directions plus an HTTP RPC endpoint). A live
browser↔JVM round-trip over Clay's websocket succeeded (see "Spike result" below),
classifying Clay as **Tier 1 (BIDIRECTIONAL)**. That is exactly the seam cositos's
host-agnostic `Model`/`Channel` already targets, so the integration is "write a
`ClayChannel`", not "reverse-engineer a kernel". No upstream patch is required (contrast
clojupyter's private emit fns / IRkernel's crash / .NET's non-standard protocol).

## Spike result (cositos-059.7, verified 2026-07-07)
All three test layers from "How we'd test this" ran green:
- **L1 JS unit** — `front/test/clay_channel.test.js`: `ClayChannel` envelope shape,
  inbound routing, Clay-frame filtering, byte-for-byte buffer round-trip vs the
  `update_nested_buffer` fixture, and a `Model` integration. 100% line coverage,
  typecheck clean, `pretender` green.
- **L2 (transport-carries-core)** — the live echo used `clojure.data.json` to round-trip
  the envelope; the protocol *core* (`clojure/src/cositos/core.clj`) remains fixture-
  certified (`clojure -M:test`, 12 tests / 30 assertions green). A full Clay transport
  wrapping the core is deferred until the adapter is built.
- **L3 live echo** — `clojure/dev/cositos/clay_spike.clj` (`:clay-spike` alias) started a
  real Clay 2.0.16 server with an `install-websocket-handler! :on-receive` echo; a real
  browser opened a websocket to it and got back both an `update` envelope
  (`{value:7, echoed:true}`) **and** a base64 buffer that decoded to `PNGDATA`
  byte-for-byte. → Clay is **Tier 1 (BIDIRECTIONAL)**, no Jupyter comm, no Clay patch.

Grounded as `dont` claim `claim:01KWYQMFQT1TNS9Q8R3HC6YH4X` (E2 ritual).
Risk #1 (buffer transport over a text frame) is now **closed** by L1 + L3.

## Background: what Clay is (amnesia-proof)
- **Clay** (`org.scicloj/clay`, current release **2.0.16**, 2026-04) is a Clojure
  library for data visualization and literate programming, driven from the REPL. You
  call `(clay/make! ...)` (or an editor shortcut) and Clay renders the evaluated forms
  to a browser tab it serves itself, and/or to a static HTML/Quarto document.
- It is **not** a Jupyter kernel. There is no `comm_open`, no `jupyter.widget` target,
  no ipywidgets layer. Rendering is driven by **Kindly** — an annotation standard
  (`kind/hiccup`, `kind/reagent`, `kind/scittle`, `kind/vega`, …) that says *how* a
  value should be visualized.
- The browser side runs **Scittle** (SCI — a ClojureScript interpreter in the page), so
  Clay can push and evaluate ClojureScript in the browser at runtime. `kind/reagent`
  mounts reactive Reagent (React) components via Scittle.

Source of truth for the transport claims below: `src/scicloj/clay/v2/server.clj` on
`scicloj/clay@main` (read 2026-07-07) and `CHANGELOG.md`.

## The decisive finding: Clay's transport is full-duplex and public
Everything a widget needs is already public API in `scicloj.clay.v2.server`:

**JVM → browser (kernel→frontend equivalent):**
- `broadcast!` — send a raw string to every connected websocket client.
- `scittle-eval-string!` (added beta50, 2025-08) — push ClojureScript to be evaluated
  in the page via `scittle.core.eval_string`.
- The browser's websocket `message` handler (see `communication-script` in
  `server.clj`) already dispatches four message shapes it receives from the JVM:
  `refresh`, `loading`, `eval-js <code>` (raw JS `eval`), and
  `scittle-eval-string <code>`.

**browser → JVM (frontend→kernel equivalent) — two independent paths:**
1. `install-websocket-handler! :on-receive #'my-handler` — registers a var called with
   `(channel, message)` for every inbound websocket message. This is the live return
   channel. (`:on-open`/`:on-close` also available.)
2. HTTP RPC (**not needed for the widget round-trip**): the `/kindly-compute` route
   (+ `install-handler!` for arbitrary Ring routes) invokes JVM functions annotated
   `:kindly/servable`, `:kindly/rpc`, or `:kindly/handler`, with content negotiation
   (Clay 2.0.5). This is a stateless request/response model that does *not* fit
   unsolicited kernel→frontend state pushes, so it is out of scope for the round-trip.
   Only potential future use: bulk binary-buffer transfer (see risk #1).

So the substrate is a **symmetric websocket** (the whole transport a widget needs) —
strictly richer than Pluto's one-way `@bind` bond, and unlike clojupyter it is all
**documented public API with no kernel internals**.

## Why this maps cleanly onto cositos
cositos's frontend is already host-agnostic (`front/src/model.js`,
`front/src/channels.js`). The `Model` speaks to a **`Channel`** seam with exactly two
methods:
- `send(msg, buffers)` — outbound `{method:"update"|"custom"|"request_state", …}`.
- `onMessage(cb)` — inbound delivery from the host.

There are already four channel implementations (Jupyter comm, `LocalChannel`,
`MemoryChannel`, `PlutoChannel`). Clay becomes a **fifth channel**. The Pluto adapter is
the precedent: a non-Jupyter host with its own comm substrate. Clay is the same idea but
*easier*, because Clay's channel is genuinely bidirectional (Pluto's `supports_receive`
is `false`; Clay's would be `true`).

### Sketch of the integration (two thin pieces, no upstream patch)
1. **Browser side — `ClayChannel` (JS/Scittle).** A `Channel` whose `send()`
   serializes the cositos `comm_msg` (plus base64/transfer-encoded buffers) and pushes
   it up Clay's websocket to the JVM; whose `onMessage` is fed by JVM→browser pushes
   (the JVM calls `scittle-eval-string!`/`broadcast!` with the frontend message, and a
   small Scittle shim routes it into the channel's inbound callback). The cositos
   `_esm` widget module and `AnyModel` are reused **verbatim** — same as every other
   host.
2. **JVM side — a Clay transport (Clojure).** Reuse the fixture-certified protocol core
   already in `clojure/src/cositos/core.clj` (message builders, buffer split/merge,
   widget-state serialization). Wire it to Clay via `install-websocket-handler!`
   (inbound `update`/`custom`/`request_state`) and `scittle-eval-string!`/`broadcast!`
   (outbound state pushes). The widget is rendered once as `kind/reagent`/`kind/hiccup`
   that boots the cositos runtime and opens the `ClayChannel`.

This is the same division of labor as the existing `clojure/` core + the (blocked)
clojupyter `Transport` adapter — except the adapter now targets Clay's public server
API instead of clojupyter's private emit fns.

## How we'd test this
The architecture makes most of the integration testable **without a live browser**.
Three layers, cheapest first:

1. **JS unit (no browser, no JVM).** Test a `ClayChannel` against a fake websocket
   object (`{ send, addEventListener }`): assert `channel.send(...)` emits the correct
   cositos envelope on the socket, and that an injected inbound frame reaches
   `Model.onMessage`. This reuses the existing `front/test/*.test.js` harness and the
   `MemoryChannel`/`LocalChannel` precedent in `front/src/channels.js`. Buffer encoding
   is verified here by asserting a `fixtures/*.json` buffer round-trips **byte-for-byte**
   through the channel's encode/decode.
2. **Protocol conformance (no browser, no Clay).** The JVM-side Clay transport wraps the
   already-certified protocol core in `clojure/src/cositos/core.clj`; feed the shared
   `fixtures/*.json` through it exactly as the Clojure core is certified today
   (`clojure -M:test`). The transport adds only websocket plumbing over a certified core.
3. **One live e2e (browser, gated, run rarely).** A single Playwright/chrome-dev-tools
   round-trip against a real Clay server — JVM push → browser Scittle → browser send →
   JVM `:on-receive` echo. This is the Tier-1 (BIDIRECTIONAL) classification and the
   *only* layer that needs a browser.

Only layer 3 is expensive; layers 1–2 run in normal CI and cover the protocol.

## Open questions / risks to verify with a spike
1. **Buffer transport over the websocket.** Clay's websocket messages are strings
   (`broadcast!`/`scittle-eval-string!` send text). cositos's protocol carries binary
   buffers out-of-band. Need to confirm whether to base64-encode buffers inline in the
   text frame, or use the HTTP RPC path for binary. (Fixtures compare raw bytes, so the
   encoding must round-trip exactly.)
2. **`scittle-eval-string!` as a data channel vs code channel.** Pushing state as
   *evaluated ClojureScript* is code injection, not data transport. Prefer routing state
   through a dedicated Scittle shim function (push `(cositos.clay/on-message <edn>)`)
   rather than eval'ing arbitrary payloads — keep the eval surface tiny.
3. **Client identity / multiplexing.** `broadcast!` hits *all* connected clients;
   `install-websocket-handler! :on-receive` gets the channel. A multi-widget page needs
   a widget-id envelope so messages route to the right `Model`. cositos already carries
   a comm/model id — reuse it as the routing key.
4. **Static export.** Clay's static HTML target has no live JVM. Widgets would degrade
   to the `LocalChannel` (client-only) mode — same story as anywidget's static HTML and
   cositos's existing static-export path. Confirm the runtime picks `ClayChannel` only
   when a live server is present.
5. **Version coupling.** `scittle-eval-string!` and `install-websocket-handler!` are
   recent (beta50 / 2.0.x). Pin `org.scicloj/clay >= 2.0.5` (RPC + handlers) and note
   the minimum in `clojure/deps.edn`.
6. **Reconnect / multi-tab (known limitation, do not solve yet).** Clay auto-reconnects
   clients (2.0.6) and `broadcast!` hits *all* clients, so after a reload or with two
   tabs widget state can desync. The eventual fix is `request_state`-on-connect, but the
   spike deliberately assumes **single client, no reconnect** — do not build
   multiplexing/resync until a real notebook needs it.

## Scope discipline (YAGNI)
Build only the **websocket `ClayChannel` + a single-widget, single-client spike**. No
HTTP RPC path, no multiplexing, no reconnect-resync, no static-export handling until a
concrete notebook demands each. The cheapest experiment that could kill the idea is
layers 1 + 3 above (JS-unit envelope test + one live echo): if the websocket can't
carry the cositos envelope, stop here.

## Recommended next steps
- **Smallest falsifiable test first.** Write a Clay round-trip **spike** (not the kernel
  probe — Clay isn't a kernel): a minimal Clay namespace that opens a websocket round
  trip (JVM push → browser Scittle → browser send → JVM `:on-receive`) and echoes a
  message. If the websocket cannot carry the cositos envelope, stop — the idea is dead.
  A passing spike classifies Clay as **Tier 1 (BIDIRECTIONAL)** empirically. Ground the
  result as a `dont` claim (E2 grounding ritual) against the spike namespace.
- **Only if the spike passes**, open a `ClayChannel` ticket (frontend) + a Clay
  transport ticket (JVM, reusing `clojure/src/cositos/core.clj`) — this **unblocks the
  Clojure interactive-widget goal** (`cositos-059.5`) via a different host than
  clojupyter, and is a cleaner path than the unverified
  `clojupyter.state/current-context` crack.
- Update `probe/README.md` with a Clay row: Clay is a *notebook tool*, not a kernel, so
  it sits outside the kernel-tier table, but the finding ("clojupyter blocked; Clay is
  the viable Clojure host") belongs next to the clojupyter entry.

## One-line takeaway
clojupyter can *receive* comms but can't *open* one from user code; Clay sidesteps the
whole comm question with a public full-duplex websocket + RPC server — making it the
recommended route to interactive cositos widgets in Clojure.
