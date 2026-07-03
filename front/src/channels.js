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
    queueMicrotask(() => this.peer?.#deliver(msg, buffers));
  }

  onMessage(cb) {
    this.#inbound = cb;
  }

  #deliver(msg, buffers) {
    this.#inbound?.(msg, buffers);
  }
}
