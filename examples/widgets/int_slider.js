// IntSlider — numeric category (ipywidgets: IntSlider/FloatSlider).
// A plain anywidget widget: works unchanged in Jupyter (via ipywidgets frontend) and
// under @cositos/front (web/wasm/pluto).
export default {
  render({ model, el }) {
    const input = document.createElement("input");
    input.type = "range";
    input.min = String(model.get("min") ?? 0);
    input.max = String(model.get("max") ?? 100);
    input.value = String(model.get("value") ?? 0);

    const label = document.createElement("span");
    const paint = () => {
      input.value = String(model.get("value"));
      label.textContent = ` ${model.get("value")}`;
    };
    paint();

    input.addEventListener("input", () => {
      model.set("value", Number(input.value));
      model.save_changes();
    });
    model.on("change:value", paint);

    el.appendChild(input);
    el.appendChild(label);
    return () => {
      input.remove();
      label.remove();
    };
  },
};
