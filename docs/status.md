---
title: "Implementation status"
---

A one-page snapshot of what's built vs. planned, so a reader doesn't have to reconstruct
it from beads issues or git history. Two independent axes decide what "works" means for a
given language: the **protocol core** (pure, fixture-certified) and **live comm** (needs a
kernel that implements Jupyter's `comm_open`/`comm_msg`, a per-kernel property, not a
per-language one—see [`probe/README.md`](https://github.com/sashakile/cositos/blob/main/probe/README.md)).

> **Note on links:** Links to per-language backends in the table below point to
> GitHub (they work on the deployed site *and* in a checkout). The `docs/` pages
> linked throughout this page are rendered as part of this Quarto site.
> See [`docs/porting.md`](porting.md) for the porting guide.

## Per-language maturity (protocol core + live comm)

The protocol core ports to a language in ~150 lines and is fixture-certified for all five
languages against the same golden fixtures (`fixtures/*.json`); see
[`docs/porting.md`](porting.md). Live widgets additionally need a kernel with real comm
support:

| Language | Protocol core | Live widgets | Detail |
|---|---|---|---|
| Python | ✅ certified | ✅ yes (Tier 1, ipykernel) | [`src/cositos/`](https://github.com/sashakile/cositos/blob/main/src/cositos/) |
| Julia | ✅ certified | ✅ yes (Tier 1, IJulia) | [`julia/README.md`](https://github.com/sashakile/cositos/blob/main/julia/README.md) |
| Clojure | ✅ certified | ✅ yes (Tier 1, via Clay) | [`clojure/`](https://github.com/sashakile/cositos/blob/main/clojure/) |
| R | ✅ certified | 🚧 blocked upstream—IRkernel's `comm$open()` throws an internal `send_response` arity error | [`r/README.md`](https://github.com/sashakile/cositos/blob/main/r/README.md) |
| C# | ✅ certified | 🚧 blocked upstream—.NET Interactive uses its own kernel protocol, doesn't answer `comm_info_request` | [`csharp/README.md`](https://github.com/sashakile/cositos/blob/main/csharp/README.md) |

"Blocked upstream" means the gap is in the kernel, not in cositos—there's no
workaround short of a protocol shim or an upstream fix. Full tier classification and how
each kernel was probed: [`probe/README.md`](https://github.com/sashakile/cositos/blob/main/probe/README.md).

## Display & hosting (static export, no kernel)

Every language port can also render **without** a live kernel by serializing a `Document`
(`dump_document`) and either displaying it in a running kernel via a `_repr_mimebundle_`
shim, or embedding it as self-contained HTML (`embed_html`) for a static host:

| Host | Kernel needed? | Status |
|---|---|---|
| Live Jupyter (any Tier‑1 kernel) | yes | shipped—`_repr_mimebundle_` |
| Static HTML export (any host) | no | shipped—`embed_html` / `write_html` |
| Voila | yes (live-serve) | recipe shipped |
| myBinder | yes (live-serve) | recipe shipped |
| Quarto | no (static embed) | shipped—this site's [home page](index.qmd) is one |
| JupyterBook | no (static embed) | recipe shipped |
| Pluto.jl | no (one-way `PlutoChannel`) | deferred—no runnable demo checked in yet |

See [`docs/hosts.md`](hosts.md) for the channel abstraction behind this table and
[`docs/tutorials/static-export.qmd`](tutorials/static-export.qmd) for the runnable recipe.

## What's deliberately not here yet

- **Interactive notebooks for R/C#**—blocked on the upstream kernel gaps above (tracked
  as beads issues; no cositos-side fix is possible until the kernel changes).
- **Pluto demo notebook**—deferred, not blocked; the channel (`PlutoChannel`) exists but
  no example notebook is checked in.
- **Publishing this site**—this Quarto site builds and renders locally
  (`mise run docs`) but isn't yet published; no hosting decision has been made yet.

## Specifications

The living specifications (protocol, serialization, embed) are woven verbatim into the
[reference → Specifications](reference/specs.qmd) page from `openspec/specs/`—that page
*is* the spec, not a paraphrase of it.

## Getting started

- [Quickstart: run your first widget](tutorials/quickstart.qmd) — pick your language
- [Architecture overview](explanation/architecture.qmd) — how cositos works
- [Author your own widget](tutorials/authoring-widgets.qmd) — write custom ESM
