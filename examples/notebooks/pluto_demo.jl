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

# ╔═╡ 23079bf6-7c6a-11f1-90df-b744befe28dd
begin
	import Pkg
	Pkg.activate(mktempdir())
	Pkg.develop(path=joinpath(@__DIR__, "..", "..", "julia"))
	Pkg.add(["AbstractPlutoDingetjes", "JSON"])
	using Cositos, AbstractPlutoDingetjes, JSON
end

# ╔═╡ 2307b0f2-7c6a-11f1-9306-a5f97ebd9615
md"""
# cositos widgets in Pluto — batteries included

No hand-written ESM, no state `Dict`, no `PlutoWidget` construction: `pluto_int_slider`,
`pluto_checkbox`, `pluto_dropdown` (and `pluto_text`/`pluto_button`/`pluto_html`) each
wrap the SAME `examples/widgets/*.js` this repo already ships and certifies
(`docs/widgets.md`'s six ipywidgets categories) into a ready-to-`@bind` `PlutoWidget`.
Nothing to configure — `runtime_url` defaults to a self-contained, offline `data:` URI
(cositos-z76.7): no npm publish, CDN, or local server.
"""

# ╔═╡ 2307c27a-7c6a-11f1-8c4b-71a9861e47d8
@bind slider_state pluto_int_slider(value=20, min=0, max=100)

# ╔═╡ 2307d5da-7c6a-11f1-9c93-b530a8e865cf
@bind checkbox_state pluto_checkbox(value=false)

# ╔═╡ 2307e78c-7c6a-11f1-a940-4981ce21c881
@bind dropdown_state pluto_dropdown(["small", "medium", "large"])

# ╔═╡ 2307f876-7c6a-11f1-93d3-3b7a884be735
md"""
Each widget above re-runs this cell reactively on interaction — every `*_state` is the
widget's full state `Dict`, exactly as `@bind` promises:

- **Slider:** $(slider_state["value"])
- **Checkbox:** $(checkbox_state["value"])
- **Dropdown:** $(dropdown_state["value"])
"""

# ╔═╡ Cell order:
# ╠═23079bf6-7c6a-11f1-90df-b744befe28dd
# ╠═2307b0f2-7c6a-11f1-9306-a5f97ebd9615
# ╠═2307c27a-7c6a-11f1-8c4b-71a9861e47d8
# ╠═2307d5da-7c6a-11f1-9c93-b530a8e865cf
# ╠═2307e78c-7c6a-11f1-a940-4981ce21c881
# ╠═2307f876-7c6a-11f1-93d3-3b7a884be735
