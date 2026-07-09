// Download-state widget (cositos-70b.5): a plain anywidget button that triggers a REAL
// browser download of the JSON string pushed into its `json` state field.
//
// Same "host owns state, widget only renders it" discipline as every other example
// widget (docs/widgets.md): this widget does no serialization itself. The host is
// responsible for putting a serialized cositos Document — typically
// `json.dumps(dump_document(entries))` — into `json` before the button becomes
// clickable; see `examples/dashboard/build.py` for the concrete Python glue.
//
// Uses a `data:` URI, not `Blob`/`URL.createObjectURL` (both are mentioned as options in
// the ticket that added this widget): a data URI needs no cleanup (no revokeObjectURL)
// and works identically in a real browser and in the jsdom-based gallery test
// (front/test/gallery.test.js) with no extra polyfill.
export default {
  render({ model, el }) {
    const button = document.createElement("button");
    const paint = () => {
      button.textContent = model.get("label") ?? "Download state";
      button.disabled = !model.get("json");
    };
    paint();
    button.addEventListener("click", () => {
      const json = model.get("json");
      if (!json) return; // nothing to download yet
      const filename = model.get("filename") ?? "cositos-state.json";
      const href = `data:application/json;charset=utf-8,${encodeURIComponent(json)}`;
      const a = document.createElement("a");
      a.href = href;
      a.download = filename;
      // Not appended to `el`: a detached anchor's .click() still triggers the browser's
      // native download prompt (per the File API/download attribute), and keeps this
      // widget's own rendered output to just the button.
      a.click();
      // Observable side effect for hosts/tests: the click succeeded and what it saved.
      model.send({ event: "download", filename, href });
    });
    model.on("change:json", paint);
    model.on("change:label", paint);
    el.appendChild(button);
    return () => button.remove();
  },
};
