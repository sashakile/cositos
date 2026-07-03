/**
 * @typedef {Object} CommMsg
 * A Jupyter widget `comm_msg` data payload (see ipywidgets messages.md v2.1.0).
 * @property {"update"|"custom"|"request_state"} method
 * @property {Object} [state]
 * @property {Array<Array<string|number>>} [buffer_paths]
 * @property {*} [content]
 *
 * @typedef {Object} Channel
 * The transport seam. A host supplies one of these.
 * @property {(msg: CommMsg, buffers?: ArrayBuffer[]) => void} send
 *   Send an outbound message toward the "kernel" side (or a local handler).
 * @property {(cb: (msg: CommMsg, buffers: ArrayBuffer[]) => void) => void} onMessage
 *   Register the model's inbound handler. The host calls it for messages arriving
 *   from the kernel side.
 */

import { remove_buffers, put_buffers } from "./buffers.js";

/**
 * A tiny event emitter keyed by event name, supporting a `context` token so all
 * listeners added by one caller can be removed at once (mirrors Backbone/anywidget).
 */
class Emitter {
  #listeners = new Map(); // name -> Array<{cb, context}>

  on(name, cb, context) {
    if (!this.#listeners.has(name)) this.#listeners.set(name, []);
    this.#listeners.get(name).push({ cb, context });
  }

  off(name, cb, context) {
    if (name == null) {
      // Remove everything for a given context (or all if context is null too).
      for (const [key, arr] of this.#listeners) {
        this.#listeners.set(
          key,
          arr.filter((l) => (context == null ? false : l.context !== context)),
        );
      }
      return;
    }
    const arr = this.#listeners.get(name) ?? [];
    this.#listeners.set(
      name,
      arr.filter((l) => (cb ? l.cb !== cb : false) && (context ? l.context !== context : true)),
    );
  }

  emit(name, ...args) {
    for (const { cb } of (this.#listeners.get(name) ?? []).slice()) cb(...args);
  }
}

/**
 * Host-agnostic AnyModel. Holds widget state, emits `change:<key>` and `msg:custom`,
 * and syncs over a {@link Channel}.
 */
export class Model {
  #state;
  #channel;
  #emitter = new Emitter();
  #dirty = new Set();

  /**
   * @param {Object} initialState
   * @param {Channel} channel
   */
  constructor(initialState, channel) {
    this.#state = { ...initialState };
    this.#channel = channel;
    channel.onMessage((msg, buffers) => this.#receive(msg, buffers ?? []));
  }

  get(key) {
    return this.#state[key];
  }

  /** Set a key locally and mark it dirty. Call {@link save_changes} to sync. */
  set(key, value) {
    this.#state[key] = value;
    this.#dirty.add(key);
    this.#emitter.emit(`change:${key}`, value);
  }

  on(name, cb, context) {
    this.#emitter.on(name, cb, context);
  }

  off(name, cb, context) {
    this.#emitter.off(name, cb, context);
  }

  /** Send all dirty keys to the kernel side as an `update` message. */
  save_changes() {
    if (this.#dirty.size === 0) return;
    const partial = {};
    for (const key of this.#dirty) partial[key] = this.#state[key];
    this.#dirty.clear();
    const { state, buffer_paths, buffers } = remove_buffers(partial);
    this.#channel.send({ method: "update", state, buffer_paths }, buffers);
  }

  /** Send a custom message (routed to the kernel's `on_custom`). */
  send(content, _callbacks, buffers) {
    this.#channel.send({ method: "custom", content }, buffers ?? []);
  }

  /** Request the full state from the kernel side. */
  request_state() {
    this.#channel.send({ method: "request_state" });
  }

  #receive(msg, buffers) {
    if (msg.method === "update") {
      const incoming = { ...(msg.state ?? {}) };
      put_buffers(incoming, msg.buffer_paths ?? [], buffers);
      for (const [key, value] of Object.entries(incoming)) {
        this.#state[key] = value;
        this.#emitter.emit(`change:${key}`, value);
      }
    } else if (msg.method === "custom") {
      this.#emitter.emit("msg:custom", msg.content, buffers);
    }
  }
}
