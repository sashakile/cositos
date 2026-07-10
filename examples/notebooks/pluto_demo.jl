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

# ╔═╡ 8a947e54-7c80-11f1-8cf2-05535da4ec14
begin
	import Pkg
	Pkg.activate(mktempdir())
	Pkg.develop(path=joinpath(@__DIR__, "..", "..", "julia"))
	Pkg.add(["AbstractPlutoDingetjes", "JSON"])
	using Cositos, AbstractPlutoDingetjes, JSON
	using Cositos.Pluto: int_slider, checkbox, dropdown
end

# ╔═╡ 8a948ff0-7c80-11f1-baf9-bdd06355d9b2
md"""
# cositos widgets in Pluto — batteries included

No hand-written ESM, no state `Dict`, no `PlutoWidget` construction:
`Cositos.Pluto.int_slider`, `checkbox`, `dropdown` (and `text`/`button`/`html`) each
wrap the SAME `examples/widgets/*.js` this repo already ships and certifies
(`docs/widgets.md`'s six ipywidgets categories) into a ready-to-`@bind` `PlutoWidget`.
`using Cositos.Pluto: int_slider, checkbox, dropdown` brings them in unqualified — no
`pluto_` prefix needed. Nothing to configure — `runtime_url` defaults to a
self-contained, offline `data:` URI (cositos-z76.7): no npm publish, CDN, or local
server.
"""

# ╔═╡ 8a94990c-7c80-11f1-b0cf-b70d3f2b6508
@bind slider_state int_slider(value=20, min=0, max=100)

# ╔═╡ 8a94a2bc-7c80-11f1-aa98-b11391b0e4a4
@bind checkbox_state checkbox(value=false)

# ╔═╡ 8a94ae88-7c80-11f1-9f3b-01bb02ba752b
@bind dropdown_state dropdown(["small", "medium", "large"])

# ╔═╡ 8a94c256-7c80-11f1-9e9a-bf4e08617f21
md"""
Each widget above re-runs this cell reactively on interaction — every `*_state` is the
widget's full state `Dict`, exactly as `@bind` promises:

- **Slider:** $(slider_state["value"])
- **Checkbox:** $(checkbox_state["value"])
- **Dropdown:** $(dropdown_state["value"])
"""

# ╔═╡ Cell order:
# ╠═8a947e54-7c80-11f1-8cf2-05535da4ec14
# ╠═8a948ff0-7c80-11f1-baf9-bdd06355d9b2
# ╠═8a94990c-7c80-11f1-b0cf-b70d3f2b6508
# ╠═8a94a2bc-7c80-11f1-aa98-b11391b0e4a4
# ╠═8a94ae88-7c80-11f1-9f3b-01bb02ba752b
# ╠═8a94c256-7c80-11f1-9e9a-bf4e08617f21
