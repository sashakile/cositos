---
title: "Hosts & channels: running cositos widgets anywhere"
---

cositos runs the **same anywidget ESM** in many environments by isolating everything
environment-specific behind one small seam: the **`Channel`**. The frontend `Model`
(from `@cositos/front`) holds widget state and syncs it over a `Channel`; a *host* (a
Jupyter kernel, a plain web page, Pluto, Clay, …) supplies the concrete channel. Porting
cositos to a new environment means writing one channel, not a new frontend.

## The `Channel` contract

A channel is any object with two methods (see `front/src/channels.js`):

```js
send(msg, buffers)      // outbound: a comm_msg toward the "kernel" side
onMessage(cb)           // register the inbound handler cb(msg, buffers)
```

`msg` is a Jupyter widget `comm_msg` payload — `{ method: "update"|"custom"|"request_state", … }`.
Binary values travel out-of-band in `buffers` (the `Model` splits them out with
`remove_buffers` and merges inbound ones with `put_buffers`, per protocol v2). A channel
may set `supports_receive = false` to declare it cannot deliver kernel→frontend messages
(one-way hosts).

The `Model` surface on top of a channel is anywidget-compatible:
`get` / `set` / `on` / `off` / `save_changes` / `send` / `request_state`.

## The built-in channels

| Channel | Host | Direction | Notes |
|---|---|---|---|
| *(native comm)* | Jupyter kernel | two-way | anywidget's own `AnyModel` over `@jupyter-widgets/base`; cositos backends speak the comm wire protocol directly (see `porting.md`). |
| `LocalChannel` | plain web page / WASM | loopback | outbound messages go to an optional handler you supply; no backend. Ideal for client-only widgets. |
| `MemoryChannel` | tests / co-located JS | two-way | `MemoryChannel.pair()` links two endpoints; each one's outbound becomes the other's inbound. |
| `PlutoChannel` | Pluto.jl | one-way (`supports_receive=false`) | maps `update` onto Pluto's `@bind` bond. See `pluto.md`. |
| `ClayChannel` | Clay (Scicloj) | two-way | rides Clay's public websocket. See below. |

### LocalChannel — client-only widgets

```js
import { Model, LocalChannel } from "@cositos/front";

let n = 0;
const channel = new LocalChannel((msg, buffers, reply) => {
  if (msg.method === "custom" && msg.content === "increment")
    reply({ method: "update", state: { value: (n += 1) }, buffer_paths: [] });
});
const model = new Model({ value: 0 }, channel);
model.send("increment"); // model.get("value") === 1, no backend involved
```

### MemoryChannel — a JS "kernel" beside a JS "frontend"

```js
const [front, kernel] = MemoryChannel.pair();
kernel.onMessage((msg) => { /* act as the kernel side */ });
const model = new Model({ value: 0 }, front);
```

## Clay (`ClayChannel`)

[Clay](https://scicloj.github.io/clay/) is Scicloj's REPL-driven Clojure notebook /
visualization tool. It is **not** a Jupyter kernel and has no comm protocol — but it runs
a **full-duplex public websocket** (`scicloj.clay.v2.server`: `broadcast!` /
`scittle-eval-string!` push to the browser; `install-websocket-handler! :on-receive`
receives from it). That is exactly enough to host a widget, with no kernel and no upstream
patch. (Clojure's kernel, clojupyter, is blocked: it can receive comms but exposes no
user-facing API to *open* one — so Clay is the recommended Clojure host. See
`probe/README.md`.)

**Wire format.** Clay frames are text, and cositos shares the socket with Clay's own
control frames (`refresh` / `loading` / `scittle-eval-string`), so cositos frames are
tagged with a `cositos ` prefix (mirroring Clay's `scittle-eval-string ` convention).
Binary buffers travel base64-encoded inline:

```
cositos {"id": "<widget-id-or-omitted>", "msg": <comm_msg>, "buffers": [<base64>, ...]}
```

**Frontend:**

```js
import { Model, ClayChannel } from "@cositos/front";

const ws = new WebSocket("ws://" + location.host);
const channel = new ClayChannel(ws /*, "widget-a" */); // optional id
const model = new Model({ count: 0 }, channel);
model.on("change:count", (v) => { /* render */ });
```

**Multiple widgets on one page** share a single socket: give each `ClayChannel` an `id`.
A channel stamps its id on outbound frames and drops inbound frames addressed to other
ids, so widgets stay independent. Omit the id for the single-widget case (nothing is
serialized, and only untagged frames are received).

**JVM side** — reuse the fixture-certified `cositos.clay` codec (`clojure/src/cositos/clay.clj`)
over Clay's server:

```clojure
(require '[cositos.clay :as tx] '[scicloj.clay.v2.server :as server])

(def state (atom {"count" 0}))

(defn on-open   [_ch]     (server/broadcast! (tx/update-frame @state)))
(defn on-receive [_ch msg]
  (when-let [parsed (tx/parse-frame msg)]                 ; nil for Clay's own frames
    (let [{:keys [type content]} (tx/apply-inbound parsed)]
      (when (and (= :custom type) (= "increment" (get content "kind")))
        (swap! state update "count" inc)
        (server/broadcast! (tx/update-frame @state))))))
```

Runnable demos live in `clojure/dev/`: `clojure -M:clay-demo` (raw counter) and
`clojure -M:clay-notebook` (rendered through Clay's `kind` system, HTML/Quarto-exportable,
two independent counters), then open `http://localhost:1971/`.

**Status / caveats.** Verified live end-to-end (a browser round-trip through the JVM;
byte-for-byte buffer fidelity; two-widget id routing). Deferred: reconnect/resync
(`request_state`-on-connect) and static-export interactivity (no live JVM → a
`LocalChannel` fallback would keep client-only widgets alive offline).

## Writing a new channel

1. Implement `send(msg, buffers)` and `onMessage(cb)`.
2. If your transport is text-only, base64-encode `buffers` (as `ClayChannel` does); if it
   is binary-capable (Jupyter comm), pass them through.
3. Set `supports_receive = false` if the host cannot push kernel→frontend messages
   mid-session (like Pluto).
4. Leave buffer *splitting* to the `Model` — use `remove_buffers` / `put_buffers` from
   `@cositos/front` only if your host also needs to split/merge on its own side.
5. Certify against the shared golden fixtures in `fixtures/*.json` so every host agrees
   byte-for-byte (see `front/test/` and `clojure/test/` for the pattern).
