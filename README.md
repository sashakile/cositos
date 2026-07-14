# cositos

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/sashakile/cositos/main?urlpath=lab/tree/examples/notebooks/python_counter.ipynb)

> A portable [anywidget](https://anywidget.dev)-inspired backend core: define a widget
> front end once, drive it from **any** Jupyter kernel language.

Try it live on myBinder — opens JupyterLab with a runnable Python widget counter
([other kernels also available](examples/binder/README.md)).

`cositos` is the small pile of protocol glue ("cositos" = little things) that sits
between a host language's state object and the Jupyter **comm** channel. It speaks the
[ipywidgets widget messaging protocol](https://github.com/jupyter-widgets/ipywidgets/blob/main/packages/schema/messages.md)
(v2.1.0) and reuses anywidget's published `AnyModel`/`AnyView` front end verbatim — so
you write **no new JavaScript** (see `docs/tutorials/authoring-widgets.qmd` to author one).

## Why

anywidget already lets you build widgets with plain ESM. Its backend has been ported to
Python and Deno, and people want Julia, C#, and R too. The blocker (per the anywidget
maintainer) is keeping the *core* free of per-language bindings. `cositos` is that
binding-free core plus a **conformance fixture suite**, so ecosystem experts can port a
backend to their language and self-certify against golden messages.

## Backend maturity

The protocol *core* ports to a language in ~150 lines and is fixture-certified for all
five backends below (see `docs/porting.md`). Whether you get **live** widgets also
depends on the kernel's comm support, which is a separate, per-kernel question — see
`probe/README.md` for how each was classified.

| Language | Live widgets today? | Detail |
|---|---|---|
| Python | ✅ yes (Tier 1, ipykernel) | [`src/cositos/`](src/cositos/) |
| Julia | ✅ yes (Tier 1, IJulia) | [`julia/README.md`](julia/README.md) |
| R | 🚧 protocol core only — blocked upstream (IRkernel comm-open bug) | [`r/README.md`](r/README.md) |
| C# | 🚧 protocol core only — blocked upstream (.NET Interactive's non-standard protocol) | [`csharp/README.md`](csharp/README.md) |
| Clojure | ✅ yes (Tier 1 via an internal-API crack, clojupyter) or via Clay (recommended, public API) | [`clojure/README.md`](clojure/README.md), [`docs/hosts.md`](docs/hosts.md#clay-claychannel) |

Full tier classification and how kernels were tested: [`probe/README.md`](probe/README.md).
Shortest runnable path per language: [`docs/tutorials/quickstart.qmd`](docs/tutorials/quickstart.qmd).

## Documentation site

The tutorials, reference, and explanation docs under `docs/` build into a Quarto
website (tutorials execute live, so a broken example fails the build, not just a lint):

```bash
mise run docs           # build docs/_site/
mise run qa-docs        # build + open it
mise run docs-preview   # live-reload preview while editing
```

Start at [`docs/index.qmd`](docs/index.qmd) (a live-rendered widget) or
[`docs/status.md`](docs/status.md) for the implementation-status overview (per-language
and per-host maturity). The site is not published yet (no hosting decision made) — build
it locally.

## Architecture

```
host state ──▶ cositos-core (pure protocol, no I/O) ──▶ Transport seam ──▶ kernel comm
                • message builders   • buffer split/merge   • mimebundle
```

- **Core is pure**: message shaping, binary-buffer split/merge, inbound parsing. No
  kernel code.
- **Transport is a seam**: each kernel supplies a thin adapter (Python `comm`,
  `Deno.jupyter.broadcast`, IJulia, dotnet-interactive). See
  `docs/tutorials/integrating.qmd` for which one to use and how to embed a widget into
  an existing tool (Quarto, JupyterBook, Voila, Clay, …).
- **Contract is data**: `fixtures/*.json` are the cross-language guarantee.

## Status

Early. The v0 core (buffers + protocol builders) is implemented and fixture-tested.
See `.wai/projects/cositos-core/` for the research → design → plan trail and
`docs/porting.md` for how to add a new-language backend.

## Development

Tooling is managed with [mise](https://mise.jdx.dev) (task runner + pinned node).

```bash
mise install     # pinned node
mise run setup   # install Python (uv) + JS (npm) deps
mise run verify  # lint + typecheck + coverage (py & js) + complexity + specs
mise tasks       # list all tasks
```

Quality gates run on every commit/push via lefthook — see [docs/hooks.md](docs/hooks.md).

## License

MITu2014see [LICENSE](LICENSE). No anywidget/ipywidgets source is vendoredu2014see [NOTICE](NOTICE)
for how cositos reuses those projects' protocol and frontend without copying source.
