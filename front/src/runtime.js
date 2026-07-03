/**
 * Widget loading + rendering. Loads an anywidget-style ESM module (a default export with
 * optional `initialize({model})` and `render({model, el})`) and drives its lifecycle —
 * exactly the contract of `@anywidget/types`, minus the Jupyter coupling.
 */

/**
 * Dynamically import an ESM source string and return its default widget definition.
 * @param {string} esm - The `_esm` source (an ES module with a default export).
 * @returns {Promise<{initialize?: Function, render?: Function}>}
 */
export async function loadWidget(esm) {
  const url = "data:text/javascript;base64," + toBase64(esm);
  const mod = await import(url);
  const def = typeof mod.default === "function" ? await mod.default() : mod.default;
  if (!def || typeof def !== "object") {
    throw new Error("[cositos] widget ESM must have a default export object or factory");
  }
  return def;
}

/**
 * Run a widget's full lifecycle against a model and a DOM element.
 * @param {{initialize?: Function, render?: Function}} widget
 * @param {{ model: import("./model.js").Model, el: HTMLElement, signal?: AbortSignal }} ctx
 * @returns {Promise<() => void>} a cleanup function
 */
export async function renderWidget(widget, { model, el, signal }) {
  const cleanups = [];
  if (widget.initialize) {
    const c = await widget.initialize({ model, signal });
    if (typeof c === "function") cleanups.push(c);
  }
  if (widget.render) {
    const c = await widget.render({ model, el, signal });
    if (typeof c === "function") cleanups.push(c);
  }
  return () => {
    for (const c of cleanups.reverse()) c();
    model.off(null, null);
  };
}

function toBase64(text) {
  if (typeof Buffer !== "undefined") return Buffer.from(text, "utf-8").toString("base64");
  // Browser path
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}
