/**
 * Channels: concrete {@link Channel} implementations for non-Jupyter hosts.
 * (A Jupyter channel wraps the kernel comm; see docs/hosts.md.)
 */

/**
 * A loopback channel with no backend. Outbound messages are delivered to an optional
 * handler you supply — ideal for pure-web widgets whose logic lives in the browser, or
 * for wiring a WASM module. If no handler is given, `save_changes`/`send` are no-ops
 * (state stays purely client-side).
 */
export class LocalChannel {
  /** @type {((msg: any, buffers: any[]) => void) | null} */
  #inbound = null;
  #handler;

  /**
   * @param {(msg, buffers, reply) => void} [handler]
   *   Called for every outbound message. `reply(msg, buffers)` pushes a message back
   *   into the model (e.g. an `update` echo or a `custom` response from WASM).
   */
  constructor(handler) {
    this.#handler = handler;
  }

  send(msg, buffers = []) {
    if (this.#handler) {
      this.#handler(msg, buffers, (m, b = []) => this.#inbound?.(m, b));
    }
  }

  onMessage(cb) {
    this.#inbound = cb;
  }
}

/**
 * An in-memory duplex channel: two endpoints whose outbound messages become the other's
 * inbound. Useful for tests and for co-locating a JS "kernel" with a JS "frontend".
 */
export class MemoryChannel {
  /** @type {((msg: any, buffers: any[]) => void) | null} */
  #inbound = null;
  /** @type {MemoryChannel|null} */
  peer = null;

  static pair() {
    const a = new MemoryChannel();
    const b = new MemoryChannel();
    a.peer = b;
    b.peer = a;
    return [a, b];
  }

  send(msg, buffers = []) {
    // Deliver asynchronously to mimic real transports and avoid re-entrancy.
    queueMicrotask(() => {
      if (this.peer) this.peer.#deliver(msg, buffers);
    });
  }

  onMessage(cb) {
    this.#inbound = cb;
  }

  #deliver(msg, buffers) {
    this.#inbound?.(msg, buffers);
  }
}

/**
 * The wire prefix for cositos frames on a Clay websocket. Clay carries text frames and
 * broadcasts control frames (`refresh`, `loading`, `scittle-eval-string ...`) to every
 * client; prefixing our frames (mirroring Clay's own `scittle-eval-string ` convention)
 * lets a shared socket carry cositos traffic without colliding with Clay's.
 */
const CLAY_PREFIX = "cositos ";

function toU8(b) {
  return b instanceof ArrayBuffer
    ? new Uint8Array(b)
    : new Uint8Array(b.buffer, b.byteOffset, b.byteLength);
}

/** base64-encode a binary value so it survives a text websocket frame. */
function encodeBuffer(b) {
  const u8 = toU8(b);
  let s = "";
  for (let i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
  return btoa(s);
}

/** Inverse of {@link encodeBuffer}; returns an ArrayBuffer (a binary value per buffers.js). */
function decodeBuffer(b64) {
  const s = atob(b64);
  const u8 = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) u8[i] = s.charCodeAt(i);
  return u8.buffer;
}

/**
 * A channel for Clay (Scicloj's REPL-driven notebook tool). Clay is not a Jupyter kernel
 * and has no comm protocol; instead it runs a websocket server (see Clay's
 * `scicloj.clay.v2.server`) that is full-duplex and public: the JVM pushes frames with
 * `broadcast!` and receives them via `install-websocket-handler! :on-receive`. This
 * channel connects to that same server as an ordinary client and exchanges cositos
 * `comm_msg` envelopes over it.
 *
 * Envelope shape (a `CLAY_PREFIX`-tagged JSON text frame):
 *   `cositos {"msg": <comm_msg>, "buffers": [<base64>, ...]}`
 * Binary buffers are base64-encoded inline because Clay frames are text.
 *
 * The socket is shared with Clay itself, so inbound frames without the prefix (Clay's own
 * `refresh`/`loading`/`scittle-eval-string` control messages) are ignored.
 */
export class ClayChannel {
  supports_receive = true;
  /** @type {((msg: any, buffers: any[]) => void) | null} */
  #inbound = null;
  #socket;
  #id;

  /**
   * @param {{ send: (data: string) => void, addEventListener: (type: string, cb: (e: {data: any}) => void) => void }} socket
   *   A WebSocket (or compatible) already connected to the Clay server.
   * @param {string|null} [id]
   *   Optional widget id for multiplexing several widgets over one socket. When set, it is
   *   stamped on outbound frames and only inbound frames with a matching id are delivered.
   *   Left null (the default), the channel is single-widget: it stamps no id and receives
   *   only untagged frames.
   */
  constructor(socket, id = null) {
    this.#socket = socket;
    this.#id = id;
    socket.addEventListener("message", (event) => this.#onFrame(event.data));
  }

  send(msg, buffers = []) {
    const envelope = { msg, buffers: buffers.map(encodeBuffer) };
    if (this.#id !== null) envelope.id = this.#id;
    this.#socket.send(CLAY_PREFIX + JSON.stringify(envelope));
  }

  onMessage(cb) {
    this.#inbound = cb;
  }

  #onFrame(data) {
    if (typeof data !== "string" || !data.startsWith(CLAY_PREFIX)) return;
    const { id = null, msg, buffers = [] } = JSON.parse(data.slice(CLAY_PREFIX.length));
    if (id !== this.#id) return; // addressed to a different widget on this shared socket
    this.#inbound?.(msg, buffers.map(decodeBuffer));
  }
}

/**
 * A channel for Pluto.jl. Pluto has no Jupyter comm; instead a widget's root element
 * acts as an `@bind` target — Pluto reads `element.value` whenever the element fires an
 * `input` event, and re-runs dependent cells. This channel therefore treats the model's
 * outbound `update` messages as "publish full state to the bond": it merges partial
 * updates into a full-state object, sets `element.value`, and dispatches `input`.
 *
 * Julia→JS mid-render push does not exist in Pluto (state arrives once, at render time,
 * embedded in the HTML), so {@link PlutoChannel#supports_receive} is `false` and custom
 * messages are surfaced to an optional sink rather than a live kernel.
 */
export class PlutoChannel {
  supports_receive = false;
  /** @type {any} */
  #state;
  #element;
  #onCustom;

  /**
   * @param {{ value: any, dispatchEvent: (e: any) => void }} element - the `@bind` element.
   * @param {object} [initialState] - the full initial state (matches the model's).
   * @param {(content: any, buffers: any[]) => void} [onCustom] - optional sink for
   *   `model.send(...)` custom messages (Pluto has no kernel to receive them).
   */
  constructor(element, initialState = {}, onCustom) {
    this.#element = element;
    this.#state = { ...initialState };
    this.#onCustom = onCustom;
    this.#publish(); // seed the bond with the initial state
  }

  send(msg, buffers = []) {
    if (msg.method === "update") {
      Object.assign(this.#state, msg.state ?? {});
      this.#publish();
    } else if (msg.method === "custom") {
      this.#onCustom?.(msg.content, buffers);
    }
  }

  onMessage(_cb) {
    // No live kernel→frontend channel in Pluto; the model is seeded with initial state
    // at construction, so there is nothing to deliver here.
  }

  #publish() {
    // Pluto's @bind reads `.value` on `input`. Setting an object value is transferred to
    // Julia as a Dict (see Bonds.transform_value on the Julia side).
    this.#element.value = { ...this.#state };
    this.#element.dispatchEvent(new CustomEvent("input", { bubbles: true }));
  }
}
