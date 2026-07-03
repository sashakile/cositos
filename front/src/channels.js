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
