# cositos

> A portable [anywidget](https://anywidget.dev)-inspired backend core: define a widget
> front end once, drive it from **any** Jupyter kernel language.

`cositos` is the small pile of protocol glue ("cositos" = little things) that sits
between a host language's state object and the Jupyter **comm** channel. It speaks the
[ipywidgets widget messaging protocol](https://github.com/jupyter-widgets/ipywidgets/blob/main/packages/schema/messages.md)
(v2.1.0) and reuses anywidget's published `AnyModel`/`AnyView` front end verbatim — so
you write **no new JavaScript**.

## Why

anywidget already lets you build widgets with plain ESM. Its backend has been ported to
Python and Deno, and people want Julia, C#, and R too. The blocker (per the anywidget
maintainer) is keeping the *core* free of per-language bindings. `cositos` is that
binding-free core plus a **conformance fixture suite**, so ecosystem experts can port a
backend to their language and self-certify against golden messages.

## Architecture

```
host state ──▶ cositos-core (pure protocol, no I/O) ──▶ Transport seam ──▶ kernel comm
                • message builders   • buffer split/merge   • mimebundle
```

- **Core is pure**: message shaping, binary-buffer split/merge, inbound parsing. No
  kernel code.
- **Transport is a seam**: each kernel supplies a thin adapter (Python `comm`,
  `Deno.jupyter.broadcast`, IJulia, dotnet-interactive).
- **Contract is data**: `fixtures/*.json` are the cross-language guarantee.

## Status

Early. The v0 core (buffers + protocol builders) is implemented and fixture-tested.
See `.wai/projects/cositos-core/` for the research → design → plan trail and
`docs/porting.md` for how to add a new-language backend.

## Development

```bash
just test      # pytest
just lint      # ruff
just check     # pretender complexity gate
```

## License

MIT — see [LICENSE](LICENSE).
