import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { JSDOM } from "jsdom";

import { PlutoChannel } from "../src/channels.js";
import { Model } from "../src/model.js";
import { loadWidget, renderWidget } from "../src/runtime.js";

const sliderESM = readFileSync(new URL("../../examples/widgets/int_slider.js", import.meta.url), "utf-8");

function setupDom() {
  const dom = new JSDOM("<!DOCTYPE html><div id='root'></div>");
  globalThis.document = dom.window.document;
  globalThis.HTMLElement = dom.window.HTMLElement;
  globalThis.CustomEvent = dom.window.CustomEvent;
  return dom;
}

test("PlutoChannel seeds the bind element with initial state on construction", () => {
  const dom = setupDom();
  const el = dom.window.document.getElementById("root");
  let inputs = 0;
  el.addEventListener("input", () => inputs++);

  new PlutoChannel(el, { value: 10, min: 0, max: 100 });

  assert.deepEqual(el.value, { value: 10, min: 0, max: 100 });
  assert.equal(inputs, 1, "must dispatch an input event so Pluto reads the bond");
  delete globalThis.document;
  delete globalThis.HTMLElement;
  delete globalThis.CustomEvent;
});

test("an anywidget ESM runs in Pluto: interaction publishes full state to the @bind element", async () => {
  const dom = setupDom();
  const el = dom.window.document.getElementById("root");
  const initial = { value: 10, min: 0, max: 100 };
  const channel = new PlutoChannel(el, initial);
  const model = new Model(initial, channel);
  await renderWidget(await loadWidget(sliderESM), { model, el });

  const inputEvents = [];
  el.addEventListener("input", () => inputEvents.push({ ...el.value }));

  // User drags the slider -> model.set + save_changes -> PlutoChannel publishes.
  const range = el.querySelector("input[type=range]");
  range.value = "55";
  range.dispatchEvent(new dom.window.Event("input"));

  // The bound element now carries the FULL state (what Julia's @bind receives).
  assert.deepEqual(el.value, { value: 55, min: 0, max: 100 });
  assert.ok(inputEvents.length >= 1, "an input event fired for Pluto to pick up");
  assert.equal(inputEvents.at(-1).value, 55);

  delete globalThis.document;
  delete globalThis.HTMLElement;
  delete globalThis.CustomEvent;
});

test("PlutoChannel routes custom messages to an optional sink (no kernel in Pluto)", () => {
  const dom = setupDom();
  const el = dom.window.document.getElementById("root");
  const seen = [];
  const channel = new PlutoChannel(el, {}, (content) => seen.push(content));
  const model = new Model({}, channel);
  model.send({ event: "click" });
  assert.deepEqual(seen, [{ event: "click" }]);
  delete globalThis.document;
  delete globalThis.HTMLElement;
  delete globalThis.CustomEvent;
});
