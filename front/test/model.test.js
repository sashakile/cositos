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
