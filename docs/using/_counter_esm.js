// Canonical counter widget ESM — reused by every language snippet in quickstart.qmd
// Changes here must be reflected in the Python, Julia, and Clojure code blocks.
export default {
  render({ model, el }) {
    const btn = document.createElement("button");
    const out = document.createElement("span");
    const paint = () => { out.textContent = " count = " + model.get("count"); };
    btn.textContent = "increment";
    btn.addEventListener("click", () => {
      model.set("count", model.get("count") + 1);
      model.save_changes();
    });
    model.on("change:count", paint);
    paint();
    el.appendChild(btn); el.appendChild(out);
  }
}