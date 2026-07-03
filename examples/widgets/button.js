// Button — button/event category (ipywidgets: Button). Uses a custom message to notify
// the kernel of clicks (ipywidgets Button emits an "on_click" event, not state).
export default {
  render({ model, el }) {
    const button = document.createElement("button");
    const paint = () => {
      button.textContent = model.get("description") ?? "Click";
    };
    paint();
    button.addEventListener("click", () => {
      model.set("clicks", (model.get("clicks") ?? 0) + 1);
      model.save_changes();
      model.send({ event: "click" });
    });
    model.on("change:description", paint);
    el.appendChild(button);
    return () => button.remove();
  },
};
