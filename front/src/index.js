/**
 * @cositos/front — a standalone, host-agnostic implementation of anywidget's
 * frontend `AnyModel` contract.
 *
 * anywidget's own frontend proxies `@jupyter-widgets/base`'s DOMWidgetModel, welding it
 * to the ipywidgets widget manager. That coupling blocks reuse outside Jupyter. This
 * package reimplements the same `AnyModel` surface (get/set/on/off/save_changes/send)
 * over a pluggable {@link Channel}, so the *same* anywidget ESM runs unchanged in
 * Jupyter, a plain web page, a WASM host, or Pluto.
 */

export { Model } from "./model.js";
export { MemoryChannel, LocalChannel, PlutoChannel, ClayChannel } from "./channels.js";
export { loadWidget, renderWidget } from "./runtime.js";
