import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { ClayChannel } from "../src/channels.js";
import { Model } from "../src/model.js";
import { remove_buffers } from "../src/buffers.js";

// L1 of the Clay-host spike (cositos-059.7): certify the ClayChannel transport WITHOUT a
// live browser or JVM. A fake WebSocket stands in for Clay's server connection. Clay
// carries text frames only, so cositos envelopes are `cositos <json>` (mirroring Clay's
// own `scittle-eval-string <code>` convention) with buffers base64-encoded inline.

const PREFIX = "cositos ";
const fixturesDir = fileURLToPath(new URL("../../fixtures/", import.meta.url));
const loadFixture = (name) =>
  JSON.parse(readFileSync(new URL(name, `file://${fixturesDir}`), "utf-8"));

/** A minimal stand-in for the browser WebSocket API surface ClayChannel uses. */
class FakeSocket {
  sent = [];
  #listeners = [];
  send(data) {
    this.sent.push(data);
  }
  addEventListener(type, cb) {
    if (type === "message") this.#listeners.push(cb);
  }
  /** Simulate a frame arriving from the Clay server. */
  receive(data) {
    for (const cb of this.#listeners) cb({ data });
  }
  lastEnvelope() {
    const frame = this.sent.at(-1);
    assert.ok(frame.startsWith(PREFIX), `frame is cositos-prefixed: ${frame}`);
    return JSON.parse(frame.slice(PREFIX.length));
  }
}

test("send() emits a cositos-prefixed envelope carrying the comm_msg", () => {
  const socket = new FakeSocket();
  const channel = new ClayChannel(socket);

  channel.send({ method: "update", state: { value: 7 }, buffer_paths: [] });

  assert.equal(socket.sent.length, 1);
  assert.deepEqual(socket.lastEnvelope(), {
    msg: { method: "update", state: { value: 7 }, buffer_paths: [] },
    buffers: [],
  });
});

test("an inbound cositos frame reaches the registered onMessage handler", () => {
  const socket = new FakeSocket();
  const channel = new ClayChannel(socket);
  const received = [];
  channel.onMessage((msg, buffers) => received.push({ msg, buffers }));

  socket.receive(
    PREFIX + JSON.stringify({ msg: { method: "custom", content: { kind: "pong" } }, buffers: [] }),
  );

  assert.deepEqual(received, [
    { msg: { method: "custom", content: { kind: "pong" } }, buffers: [] },
  ]);
});

test("ClayChannel ignores Clay's own broadcast frames", () => {
  const socket = new FakeSocket();
  const channel = new ClayChannel(socket);
  const received = [];
  channel.onMessage((msg) => received.push(msg));

  // Frames the Clay server broadcasts to every client (server.clj communication-script).
  socket.receive("refresh");
  socket.receive("loading");
  socket.receive("scittle-eval-string (println :hi)");

  assert.deepEqual(received, [], "non-cositos frames must not reach the model");
});

test("buffers round-trip byte-for-byte through the text frame (update_nested_buffer fixture)", () => {
  const fx = loadFixture("update_nested_buffer.json");
  const socket = new FakeSocket();
  const channel = new ClayChannel(socket);

  // Same input the conformance test uses; split buffers exactly as the model would.
  const input = { img: { bytes: new Uint8Array(Buffer.from("PNGDATA")) }, shape: [1, 1] };
  const { state, buffer_paths, buffers } = remove_buffers(input);
  channel.send({ method: "update", state, buffer_paths }, buffers);

  // Outbound: the envelope encodes the buffer exactly as the golden fixture's base64.
  const envelope = socket.lastEnvelope();
  assert.deepEqual(envelope.buffers, fx.buffers_b64);

  // Inbound: decoding the same envelope yields the original bytes, byte-for-byte.
  const decoded = [];
  channel.onMessage((_msg, bufs) => decoded.push(...bufs));
  socket.receive(PREFIX + JSON.stringify(envelope));
  assert.deepEqual(new Uint8Array(decoded[0]), new Uint8Array(Buffer.from("PNGDATA")));
});

test("Model over ClayChannel: set+save_changes emits an update; inbound update applies", () => {
  const socket = new FakeSocket();
  const channel = new ClayChannel(socket);
  const model = new Model({ value: 0 }, channel);

  model.set("value", 7);
  model.save_changes();
  assert.deepEqual(socket.lastEnvelope().msg, {
    method: "update",
    state: { value: 7 },
    buffer_paths: [],
  });

  const seen = [];
  model.on("change:value", (v) => seen.push(v));
  socket.receive(
    PREFIX + JSON.stringify({ msg: { method: "update", state: { value: 42 }, buffer_paths: [] }, buffers: [] }),
  );
  assert.equal(model.get("value"), 42);
  assert.deepEqual(seen, [42]);
});
