// Text — string category (ipywidgets: Text/Textarea).
export default {
  render({ model, el }) {
    const input = document.createElement("input");
    input.type = "text";
    const paint = () => {
      if (input.value !== model.get("value")) input.value = model.get("value") ?? "";
    };
    paint();
    input.addEventListener("input", () => {
      model.set("value", input.value);
      model.save_changes();
    });
    model.on("change:value", paint);
    el.appendChild(input);
    return () => input.remove();
  },
};
