// Dropdown — selection category (ipywidgets: Dropdown/Select/RadioButtons).
export default {
  render({ model, el }) {
    const select = document.createElement("select");
    const build = () => {
      select.innerHTML = "";
      for (const opt of model.get("options") ?? []) {
        const o = document.createElement("option");
        o.value = String(opt);
        o.textContent = String(opt);
        select.appendChild(o);
      }
      select.value = String(model.get("value"));
    };
    build();
    select.addEventListener("change", () => {
      model.set("value", select.value);
      model.save_changes();
    });
    model.on("change:value", () => {
      select.value = String(model.get("value"));
    });
    model.on("change:options", build);
    el.appendChild(select);
    return () => select.remove();
  },
};
