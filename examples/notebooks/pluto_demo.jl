### A Pluto.jl notebook ###
# v1.0.3

using Markdown
using InteractiveUtils

# This Pluto notebook uses @bind for interactivity. When running this notebook outside of Pluto, the following 'mock version' of @bind gives bound variables a default value (instead of an error).
macro bind(def, element)
    #! format: off
    return quote
        local iv = try Base.loaded_modules[Base.PkgId(Base.UUID("6e696c72-6542-2067-7265-42206c756150"), "AbstractPlutoDingetjes")].Bonds.initial_value catch; b -> missing; end
        local el = $(esc(element))
        global $(esc(def)) = Core.applicable(Base.get, el) ? Base.get(el) : iv(el)
        el
    end
    #! format: on
end

# ╔═╡ a860f54a-7c60-11f1-8410-1921fa53d0ae
begin
	import Pkg
	Pkg.activate(mktempdir())
	Pkg.develop(path=joinpath(@__DIR__, "..", "..", "julia"))
	Pkg.add(["AbstractPlutoDingetjes", "JSON"])
	using Cositos, AbstractPlutoDingetjes, JSON
end

# ╔═╡ a86108a0-7c60-11f1-b8c1-052bf1c22b82
md"""
# cositos widget in Pluto — no npm publish required

Pluto is **not** Jupyter — see `docs/pluto.md` for how `PlutoWidget` maps anywidget's
`AnyModel`/`@bind` reactivity onto Pluto's model. This notebook reuses the exact same
anywidget ESM the Python/Julia/Clojure Jupyter counters use for the slider category
(`examples/widgets/int_slider.js`) and drives it with `Cositos.local_front_runtime_url()`
— a `data:` URI bundling `@cositos/front` (`front/src/*.js`) with **zero** npm publish,
CDN, or local server (cositos-z76.7). Works fully offline.
"""

# ╔═╡ a8612c36-7c60-11f1-9e8f-3f24b35eb6e3
const SLIDER_ESM = read(joinpath(@__DIR__, "..", "widgets", "int_slider.js"), String)

# ╔═╡ a86154ea-7c60-11f1-9306-3791da66fbd8
@bind widget_state PlutoWidget(
	esm=SLIDER_ESM,
	state=Dict("value" => 20, "min" => 0, "max" => 100),
	runtime_url=Cositos.local_front_runtime_url(),
)

# ╔═╡ a8616764-7c60-11f1-87b2-71aa460983c3
md"""
Dragging the slider above re-runs this cell reactively — `widget_state` is the widget's
full state `Dict`, exactly as `@bind` promises:

**Current value:** $(widget_state["value"])
"""

# ╔═╡ Cell order:
# ╠═a860f54a-7c60-11f1-8410-1921fa53d0ae
# ╠═a86108a0-7c60-11f1-b8c1-052bf1c22b82
# ╠═a8612c36-7c60-11f1-9e8f-3f24b35eb6e3
# ╠═a86154ea-7c60-11f1-9306-3791da66fbd8
# ╠═a8616764-7c60-11f1-87b2-71aa460983c3
