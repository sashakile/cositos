import assert from "node:assert/strict";
import { test } from "node:test";

import { MemoryChannel, LocalChannel } from "../src/channels.js";
import { Model } from "../src/model.js";

const tick = () => new Promise((r) => setTimeout(r, 0));

test("set + save_changes sends an update over the channel", async () => {
  const [front, kernel] = MemoryChannel.pair();
  const received = [];
  kernel.onMessage((msg) => received.push(msg));
  const model = new Model({ value: 0 }, front);

  model.set("value", 7);
  model.save_changes();
  await tick();

  assert.deepEqual(received, [{ method: "update", state: { value: 7 }, buffer_paths: [] }]);
});

test("inbound update applies state and fires change events", async () => {
  const [front, kernel] = MemoryChannel.pair();
  const model = new Model({ value: 0 }, front);
  const seen = [];
  model.on("change:value", (v) => seen.push(v));

  kernel.send({ method: "update", state: { value: 42 }, buffer_paths: [] });
  await tick();

  assert.equal(model.get("value"), 42);
  assert.deepEqual(seen, [42]);
});

test("send emits a custom message; inbound custom fires msg:custom", async () => {
  const [front, kernel] = MemoryChannel.pair();
  const kernelMsgs = [];
  kernel.onMessage((msg) => kernelMsgs.push(msg));
  const model = new Model({}, front);

  model.send({ kind: "ping" });
  await tick();
  assert.deepEqual(kernelMsgs, [{ method: "custom", content: { kind: "ping" } }]);

  const got = [];
  model.on("msg:custom", (c) => got.push(c));
  kernel.send({ method: "custom", content: { kind: "pong" } });
  await tick();
  assert.deepEqual(got, [{ kind: "pong" }]);
});

test("request_state sends a request_state message over the channel", async () => {
  const [front, kernel] = MemoryChannel.pair();
  const msgs = [];
  kernel.onMessage((m) => msgs.push(m));
  const model = new Model({}, front);

  model.request_state();
  await tick();

  assert.deepEqual(msgs, [{ method: "request_state" }]);
});

test("off(name, cb) removes only that callback, leaving others", () => {
  const [front] = MemoryChannel.pair();
  const model = new Model({ value: 0 }, front);
  const seen = [];
  const a = (v) => seen.push(["a", v]);
  const b = (v) => seen.push(["b", v]);
  model.on("change:value", a);
  model.on("change:value", b);

  model.off("change:value", a);
  model.set("value", 1);

  assert.deepEqual(seen, [["b", 1]]);
});

test("off(null, null, context) removes only that context's listeners", () => {
  const [front] = MemoryChannel.pair();
  const model = new Model({ value: 0 }, front);
  const seen = [];
  const ctx = {};
  model.on("change:value", (v) => seen.push(["ctx", v]), ctx);
  model.on("change:value", (v) => seen.push(["free", v]));

  model.off(null, null, ctx);
  model.set("value", 5);

  assert.deepEqual(seen, [["free", 5]]);
});

test("off(name) with no callback clears all listeners; unknown name is a no-op", () => {
  const [front] = MemoryChannel.pair();
  const model = new Model({ value: 0 }, front);
  const seen = [];
  model.on("change:value", (v) => seen.push(v));

  model.off("no-such-event"); // unknown name -> ?? [] fallback, no-op
  model.off("change:value"); // no cb -> drops every listener for the name
  model.set("value", 3);

  assert.deepEqual(seen, []);
});

test("off(name, cb, context) matches on both callback and context", () => {
  const [front] = MemoryChannel.pair();
  const model = new Model({ value: 0 }, front);
  const seen = [];
  const ctx = {};
  const fn = (v) => seen.push(v);
  model.on("change:value", fn, ctx);

  model.off("change:value", fn, ctx);
  model.set("value", 9);

  assert.deepEqual(seen, []);
});

test("save_changes with nothing dirty sends nothing", async () => {
  const [front, kernel] = MemoryChannel.pair();
  const msgs = [];
  kernel.onMessage((m) => msgs.push(m));
  const model = new Model({ value: 0 }, front);

  model.save_changes();
  await tick();

  assert.deepEqual(msgs, []);
});

test("inbound update tolerates a missing buffers arg and missing state/buffer_paths", () => {
  // A minimal channel that invokes the model's handler with a single argument,
  // exercising the `buffers ?? []` and `state/buffer_paths ?? {}` fallbacks.
  let deliver;
  const channel = {
    send() {},
    onMessage(cb) {
      deliver = cb;
    },
  };
  const model = new Model({ value: 0 }, channel);
  const seen = [];
  model.on("change:value", (v) => seen.push(v));

  deliver({ method: "update", state: { value: 7 } }); // no buffers, no buffer_paths

  assert.equal(model.get("value"), 7);
  assert.deepEqual(seen, [7]);
});

test("LocalChannel with a reducer enables a backend-less widget", () => {
  // A pure-web widget: clicking increments locally via a JS reducer, no kernel.
  const channel = new LocalChannel((msg, _buffers, reply) => {
    if (msg.method === "custom" && msg.content === "increment") {
      reply({ method: "update", state: { value: (current += 1) }, buffer_paths: [] });
    }
  });
  let current = 0;
  const model = new Model({ value: 0 }, channel);
  model.send("increment");
  assert.equal(model.get("value"), 1);
  model.send("increment");
  assert.equal(model.get("value"), 2);
});
