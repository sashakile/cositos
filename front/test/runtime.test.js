import assert from "node:assert/strict";
import { test } from "node:test";

import { JSDOM } from "jsdom";

import { MemoryChannel } from "../src/channels.js";
import { Model } from "../src/model.js";
import { loadWidget, renderWidget } from "../src/runtime.js";

/**
 * This is an UNMODIFIED anywidget-style widget: a default export with a `render`
 * function taking `{ model, el }` and using `model.get/set/save_changes/on`. If this
 * runs under cositos-front, then the anywidget authoring model is reusable outside
 * Jupyter (pure web, WASM, Pluto) with no code changes.
 */
const COUNTER_ESM = `
export default {
  render({ model, el }) {
    const btn = document.createElement("button");
    const paint = () => { btn.innerHTML = "count is " + model.get("value"); };
    paint();
    btn.addEventListener("click", () => {
      model.set("value", model.get("value") + 1);
      model.save_changes();
    });
    model.on("change:value", paint);
    el.appendChild(btn);
    return () => btn.remove();
  }
};
`;

test("loadWidget uses the browser base64 path when Buffer is unavailable", async () => {
  // Force the TextEncoder + btoa fallback (runtime.js) that browsers/WASM hosts take.
  const savedBuffer = globalThis.Buffer;
  try {
    globalThis.Buffer = undefined;
    const widget = await loadWidget(`export default { render() {} }`);
    assert.equal(typeof widget.render, "function");
  } finally {
    globalThis.Buffer = savedBuffer;
  }
});

test("anywidget-authored ESM renders and reacts under cositos-front (no Jupyter)", async () => {
  const dom = new JSDOM("<!DOCTYPE html><div id='root'></div>");
  globalThis.document = dom.window.document;
  globalThis.HTMLElement = dom.window.HTMLElement;

  const [front, kernel] = MemoryChannel.pair();
  const model = new Model({ value: 10 }, front);
  const el = dom.window.document.getElementById("root");

  const widget = await loadWidget(COUNTER_ESM);
  const cleanup = await renderWidget(widget, { model, el });

  const button = el.querySelector("button");
  assert.equal(button.innerHTML, "count is 10");

  // User interaction updates model state and re-renders — the AnyModel contract works.
  button.dispatchEvent(new dom.window.Event("click"));
  assert.equal(model.get("value"), 11);
  assert.equal(button.innerHTML, "count is 11");

  // A kernel-side update flows back into the same widget and re-paints it.
  kernel.send({ method: "update", state: { value: 99 }, buffer_paths: [] });
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(button.innerHTML, "count is 99");

  cleanup();
  assert.equal(el.querySelector("button"), null);

  delete globalThis.document;
  delete globalThis.HTMLElement;
});
