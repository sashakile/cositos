// Checkbox — boolean category (ipywidgets: Checkbox/ToggleButton).
export default {
  render({ model, el }) {
    const input = document.createElement("input");
    input.type = "checkbox";
    const paint = () => {
      input.checked = Boolean(model.get("value"));
    };
    paint();
    input.addEventListener("change", () => {
      model.set("value", input.checked);
      model.save_changes();
    });
    model.on("change:value", paint);
    el.appendChild(input);
    return () => input.remove();
  },
};
