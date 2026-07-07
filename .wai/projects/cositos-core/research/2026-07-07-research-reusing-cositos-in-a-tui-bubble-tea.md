# Research: Reusing cositos in a TUI (Bubble Tea, Ratatui, Textual)

> **Status: research only, parked for later.** No implementation planned yet.
> Captures the feasibility analysis so a future session can resume cold.

## Question
Can cositos be reused to drive a **terminal user interface (TUI)** instead of a
browser/Jupyter frontend? And how do established TUI frameworks—Bubble Tea (Go),
Ratatui (Rust), Textual (Python)—solve the state/reactivity/rendering problem, so we
can judge what (if anything) is reusable in either direction?

## Answer in one line
**The *wire* reuses; the *view* doesn't.** cositos-core (protocol builders + binary
buffer split/merge + inbound parser + the `Transport` seam) is pure and browser-free, so
a TUI is "just another host adapter" on the transport side. But cositos's *view* is
anywidget's ESM/DOM frontend, which is fundamentally browser-bound—a terminal has no
DOM and no JS engine. A TUI must supply its own terminal renderer. The strongest reuse is
**Textual's reactive-attribute model** as a Python-native cositos TUI frontend, because
its `reactive`/`watch_` descriptors are a near-clone of the traitlets/anywidget observable
trait model cositos already targets.

## Background: What cositos is (amnesia-proof)
cositos is a binding-free core that shuttles [ipywidgets comm-protocol](https://github.com/jupyter-widgets/ipywidgets/blob/main/packages/schema/messages.md)
(v2.1.0) messages between a host-language state object and a frontend, reusing anywidget's
published `AnyModel`/`AnyView` JS frontend verbatim. Two sides:
- **Python core** (`src/cositos/`): `protocol.py` (message builders + inbound parser),
  `buffers.py` (binary split/merge), `model.py` (`Widget` façade), `transport.py` (the
  `Transport` Protocol—the *only* kernel-facing seam, and it makes **no** browser
  assumption). `jupyter.py`'s `CommTransport` is one concrete adapter.
- **JS frontend** (`front/src/`): a host-agnostic `Model` + a `Channel` seam
  (`LocalChannel`, `MemoryChannel`, `ClayChannel`, `PlutoChannel`), plus `runtime.js`
  which loads a widget's `_esm` and calls `render({model, el})` against an `HTMLElement`.

The "things" cositos does are: (1) hold observable widget state, (2) react to state
changes by re-rendering, (3) shuttle state changes across a boundary. cositos nails (3)
but has **no** answer for (1)+(2) in a terminal—that's exactly what TUI frameworks
provide.

## How the TUI frameworks solve it (verified against current docs/source, 2026-07-07)

| Framework | Lang | State model | Render model | Event/sync model |
|---|---|---|---|---|
| **Bubble Tea** (+Bubbles component lib = "bubblegum") | Go | Immutable `Model` struct | `View() string` → cell-based renderer | **The Elm Architecture**: `Update(Msg) (Model, Cmd)`. All IO funnels through `Msg`; side effects return via `Cmd`. |
| **Ratatui** | Rust | *You own it* (no built-in store) | **Immediate mode**: `terminal.draw(\|f\| …)` rebuilds widgets every frame, diffs the buffer. `StatefulWidget` has an associated `State` passed in at render (list selection, scrollbar pos). | None built-in; docs *recommend* layering TEA on top. |
| **Textual** | Python | `reactive(default)` descriptors with `validate_`, `watch_`, `compute_`, `data_bind` | "Smart refresh": mutating a reactive automatically calls `render()` | DOM-like widget tree, message bubbling |

**Key observation:** Textual's `reactive` + `watch_` is the same observable-attribute
model as traitlets/anywidget (observable attribute → callback → re-render)—precisely
what cositos's frontend `Model` (`change:<key>` emitter) and the kernel-side trait object
assume. Bubble Tea's Msg/Cmd loop is the same shape as cositos's inbound
`update`/`custom`/`request_state` + outbound `send`. Ratatui's "pure render, external
state" split mirrors cositos's "core is pure, host owns state" discipline; Bubbles
components are themselves TEA models composed into a parent.

Sources (verified via curl):
- Bubble Tea README: "A Go framework based on The Elm Architecture … model + Init/Update/View."
- Ratatui README + `ratatui.rs/concepts/rendering`—immediate mode; `docs.rs`
  `StatefulWidget` trait has an associated `State` type + `render_stateful_widget`.
- Textual `docs/guide/reactivity.md`—`reactive()`, `validate_`, `watch_`, `compute_`,
  smart refresh, `data_bind`.

## Reuse analysis

### Reuse code directly: No
cositos is Python protocol glue + a JS/DOM frontend; the frameworks are Go, Rust, and
terminal-Python. No shared artifact to import. But the architectures line up well enough
that integration is thin glue, not a rewrite.

### Direction A: Cositos borrows the view it lacks (recommended: Textual)
Textual is the natural substrate for a cositos TUI frontend: Python (same as the
reference language implementation) and trait-shaped reactivity.

```
kernel state ──cositos-core (protocol)──▶ TuiTransport ──▶ Textual reactive attr
   ▲                                                          │ watch_<key>() → smart refresh
   └──────── send_state (update msg) ◀── terminal input ──────┘
```

- Inbound comm `update` → assign a Textual `reactive` → `watch_` fires → auto re-render.
  Zero impedance mismatch.
- Terminal keypress → mutate reactive → adapter sends an `update` back over `TuiTransport`.
- **You render terminal widgets by convention keyed on state—you don't execute the
  anywidget `_esm`.** That's the unavoidable cost (the DOM view doesn't survive), but it's
  small new code, not a language port.

Bubble Tea works identically in Go (Msg = inbound comm message, Cmd = outbound send) but
requires **porting cositos-core to Go**—a legitimate new cositos language port. Ratatui is the
most manual (you own state, call `send_state` on mutation, hand-roll the TEA loop the docs
recommend).

### Direction B: The TUI borrows cositos's remoting (the novel combination)
Bubble Tea, Ratatui, and Textual all assume the UI and app logic are **in-process and the
same language**. None has a remoting/wire story. cositos's fixture-certified comm protocol
*is* that missing layer. The genuinely novel combination:

> A Textual (or Bubble Tea) terminal UI **driven by a Jupyter kernel in a different
> language** (Julia/C#/R) over cositos comm messages.

None of the frameworks can do this alone; it's squarely in cositos's wheelhouse—the TUI
is another host adapter on the `Transport` seam. cositos supplies the *wire + cross-language
state parity*; the framework supplies the *widgets*. The union is strictly more capable
than either alone.

## What's not reusable
The view. anywidget's ESM is browser/DOM-bound (`runtime.renderWidget` needs an
`HTMLElement`; `embed.py` is CDN html-manager; state carries `_esm` + `_model_module:
anywidget`). Every TUI framework replaces it with its own terminal renderer. There is no
view seam analogous to the transport seam.

## Suggested next steps (when picked up)
1. **Spike the Textual path** (lowest risk, Python-native): a `TuiTransport` (loopback,
   `supports_receive=True`) + a Textual reactive bridge driving one `examples/widgets/`
   state through the real cositos core. Prove the round-trip: kernel `send_state` →
   `watch_` re-render; terminal input → inbound `update` → `set_state`.
2. If Direction B is wanted, scope a **Go cositos-core port** as a new language implementation (fixture
   suite is the contract) and a Bubble Tea Msg/Cmd ⇄ comm bridge.
3. Add a `coverage-manifest.toml` entry for any new language-port dir in the same commit (E1
   ritual); ground any new empirical capability claim via `dont` (E2 ritual).

## Open questions
- Does a "render by convention" mapping (state key → terminal widget) generalize, or does
  every widget need a bespoke Textual view? (Likely bespoke—same as anywidget authors
  writing per-widget ESM.)
- Is there value in a *shared* declarative view spec that both an ESM frontend and a
  Textual frontend could consume? (Out of scope; would erode the "reuse anywidget's
  frontend verbatim" premise.)

