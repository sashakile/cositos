import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { JSDOM } from "jsdom";

import { MemoryChannel } from "../src/channels.js";
import { Model } from "../src/model.js";
import { loadWidget, renderWidget } from "../src/runtime.js";

// Proves one AnyModel + @cositos/front cover the whole ipywidgets category surface,
// using UNMODIFIED anywidget-style ESM from examples/widgets/. No @jupyter-widgets zoo.

const widgetsDir = new URL("../../examples/widgets/", import.meta.url);
const load = (name) => readFileSync(new URL(name, widgetsDir), "utf-8");

const tick = () => new Promise((r) => setTimeout(r, 0));

function mount(initialState) {
  const dom = new JSDOM("<!DOCTYPE html><div id='root'></div>");
  globalThis.document = dom.window.document;
  globalThis.HTMLElement = dom.window.HTMLElement;
  const [front, kernel] = MemoryChannel.pair();
  const model = new Model(initialState, front);
  const el = dom.window.document.getElementById("root");
  return { dom, model, kernel, el };
}

function unmount() {
  delete globalThis.document;
  delete globalThis.HTMLElement;
}

test("numeric: int_slider syncs value both ways", async () => {
  const { dom, model, kernel, el } = mount({ value: 10, min: 0, max: 100 });
  const cleanup = await renderWidget(await loadWidget(load("int_slider.js")), { model, el });
  const input = el.querySelector("input[type=range]");
  assert.equal(input.value, "10");

  input.value = "55";
  input.dispatchEvent(new dom.window.Event("input"));
  assert.equal(model.get("value"), 55);

  kernel.send({ method: "update", state: { value: 80 }, buffer_paths: [] });
  await tick();
  assert.equal(input.value, "80");
  cleanup();
  unmount();
});

test("boolean: checkbox toggles", async () => {
  const { dom, model, el } = mount({ value: false });
  const cleanup = await renderWidget(await loadWidget(load("checkbox.js")), { model, el });
  const box = el.querySelector("input[type=checkbox]");
  box.checked = true;
  box.dispatchEvent(new dom.window.Event("change"));
  assert.equal(model.get("value"), true);
  cleanup();
  unmount();
});

test("string: text edits", async () => {
  const { dom, model, el } = mount({ value: "hi" });
  const cleanup = await renderWidget(await loadWidget(load("text.js")), { model, el });
  const input = el.querySelector("input[type=text]");
  assert.equal(input.value, "hi");
  input.value = "world";
  input.dispatchEvent(new dom.window.Event("input"));
  assert.equal(model.get("value"), "world");
  cleanup();
  unmount();
});

test("button: click bumps state and sends a custom event", async () => {
  const { dom, model, kernel, el } = mount({ description: "Go", clicks: 0 });
  const custom = [];
  kernel.onMessage((msg) => msg.method === "custom" && custom.push(msg.content));
  const cleanup = await renderWidget(await loadWidget(load("button.js")), { model, el });
  const button = el.querySelector("button");
  assert.equal(button.textContent, "Go");
  button.dispatchEvent(new dom.window.Event("click"));
  await tick();
  assert.equal(model.get("clicks"), 1);
  assert.deepEqual(custom, [{ event: "click" }]);
  cleanup();
  unmount();
});

test("selection: dropdown picks an option", async () => {
  const { dom, model, el } = mount({ options: ["a", "b", "c"], value: "a" });
  const cleanup = await renderWidget(await loadWidget(load("dropdown.js")), { model, el });
  const select = el.querySelector("select");
  assert.equal(select.options.length, 3);
  select.value = "c";
  select.dispatchEvent(new dom.window.Event("change"));
  assert.equal(model.get("value"), "c");
  cleanup();
  unmount();
});

test("output: html renders and reacts to kernel updates", async () => {
  const { model, kernel, el } = mount({ value: "<b>hi</b>" });
  const cleanup = await renderWidget(await loadWidget(load("html.js")), { model, el });
  assert.equal(el.querySelector("div b").textContent, "hi");
  kernel.send({ method: "update", state: { value: "<i>bye</i>" }, buffer_paths: [] });
  await tick();
  assert.equal(el.querySelector("div i").textContent, "bye");
  cleanup();
  unmount();
});
