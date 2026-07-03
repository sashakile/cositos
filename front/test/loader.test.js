import assert from "node:assert/strict";
import { test } from "node:test";

import { MemoryChannel } from "../src/channels.js";
import { Model } from "../src/model.js";
import { loadWidget, renderWidget } from "../src/runtime.js";

test("loadWidget accepts a factory-function default export", async () => {
  const esm = `export default () => ({ render() {} });`;
  const widget = await loadWidget(esm);
  assert.equal(typeof widget.render, "function");
});

test("loadWidget rejects a non-object default export", async () => {
  await assert.rejects(() => loadWidget(`export default 42;`), /default export object or factory/);
});

test("renderWidget runs initialize then render and returns a cleanup", async () => {
  const order = [];
  const widget = {
    initialize() {
      order.push("init");
      return () => order.push("init-cleanup");
    },
    render() {
      order.push("render");
      return () => order.push("render-cleanup");
    },
  };
  const [front] = MemoryChannel.pair();
  const model = new Model({}, front);
  const cleanup = await renderWidget(widget, { model, el: {} });
  assert.deepEqual(order, ["init", "render"]);
  cleanup();
  // cleanups run in reverse registration order
  assert.deepEqual(order, ["init", "render", "render-cleanup", "init-cleanup"]);
});

test("renderWidget tolerates a widget with no lifecycle hooks", async () => {
  const [front] = MemoryChannel.pair();
  const cleanup = await renderWidget({}, { model: new Model({}, front), el: {} });
  assert.equal(typeof cleanup, "function");
  cleanup();
});
