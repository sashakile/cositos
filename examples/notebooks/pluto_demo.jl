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

# ╔═╡ 87907f98-7c65-11f1-bc5c-2dbaa642ebb3
begin
	import Pkg
	Pkg.activate(mktempdir())
	Pkg.develop(path=joinpath(@__DIR__, "..", "..", "julia"))
	Pkg.add(["AbstractPlutoDingetjes", "JSON"])
	using Cositos, AbstractPlutoDingetjes, JSON
end

# ╔═╡ 87909280-7c65-11f1-ab5d-abcb439a5798
md"""
# cositos widget in Pluto — no npm publish required

Pluto is **not** Jupyter — see `docs/pluto.md` for how `PlutoWidget` maps anywidget's
`AnyModel`/`@bind` reactivity onto Pluto's model. This notebook reuses the exact same
anywidget ESM the Python/Julia/Clojure Jupyter counters use for the slider category
(`examples/widgets/int_slider.js`). `PlutoWidget`'s `runtime_url` defaults to a
self-contained, offline `data:` URI bundling `@cositos/front` (`front/src/*.js`) — no
npm publish, CDN, or local server required (cositos-z76.7); nothing to configure below.
"""

# ╔═╡ 8790a496-7c65-11f1-b5ef-152829f72351
const SLIDER_ESM = read(joinpath(@__DIR__, "..", "widgets", "int_slider.js"), String)

# ╔═╡ 8790b224-7c65-11f1-b8c1-b18b22751bc6
@bind widget_state PlutoWidget(esm=SLIDER_ESM, state=Dict("value" => 20, "min" => 0, "max" => 100))

# ╔═╡ 8790be1a-7c65-11f1-939b-d3366e48ada0
md"""
Dragging the slider above re-runs this cell reactively — `widget_state` is the widget's
full state `Dict`, exactly as `@bind` promises:

**Current value:** $(widget_state["value"])
"""

# ╔═╡ Cell order:
# ╠═87907f98-7c65-11f1-bc5c-2dbaa642ebb3
# ╠═87909280-7c65-11f1-ab5d-abcb439a5798
# ╠═8790a496-7c65-11f1-b5ef-152829f72351
# ╠═8790b224-7c65-11f1-b8c1-b18b22751bc6
# ╠═8790be1a-7c65-11f1-939b-d3366e48ada0
