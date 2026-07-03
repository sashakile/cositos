// HTML — output/display category (ipywidgets: HTML/Label/Output).
export default {
  render({ model, el }) {
    const div = document.createElement("div");
    const paint = () => {
      div.innerHTML = model.get("value") ?? "";
    };
    paint();
    model.on("change:value", paint);
    el.appendChild(div);
    return () => div.remove();
  },
};
