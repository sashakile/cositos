# Cross-language e2e examples: The shared contract

This directory holds one self-certifying end-to-end (**e2e**) example per language port.
Each proves that a language's cositos port produces the *exact* same widget-state
document as the Python reference, so the ports can never silently drift.

Run them all with one command:

```bash
mise run e2e-all
```

The orchestrator (`scripts/e2e_all.py`) runs every language in isolation and prints a
per-language `OK` / `SKIP` / `FAIL` summary:

- a language whose **runtime isn't installed**: `SKIP` (never a failure);
- a language whose e2e task **isn't implemented yet**: `SKIP` (transitional);
- a language that **runs and passes**: `OK`;
- a language that **diverges or errors**: `FAIL`.

`mise run e2e-all` exits non-zero **if and only if at least one language FAILed**. A
`SKIP` isn't a failure, so a machine missing (say) Julia or .NET still certifies every
language it *can*. This is deliberately decoupled from the Quarto docs render
(`docs/tutorials/polyglot-parity.qmd`), which aborts the *whole* site build on any
divergence. Here, one broken language never masks the others.

## The contract every language program MUST satisfy

Each per-language example is a standalone program invoked by a mise task named
`e2e-<lang>` (for example `e2e-python` or `e2e-julia`). To conform, the program must:

1. **Build a widget-state `Document` from the FIXED input state below**: an anywidget
   counter, a single model with id `counter` and state `{_esm, value: 42}`. The `_esm` is
   the exact string in [The fixed input](#the-fixed-input). No other models, no buffers.

2. **Assert the round-trip law `load(dump(x)) == x`.** Serialize the counter to the
   `Document`, then deserialize it back and assert it equals the original input state.
   What "load" means is language-specific (deserialize the document back into the port's
   native model representation), but the law is the same everywhere.

3. **Diff the produced `Document` against [`expected.json`](./expected.json)**, the pinned
   golden document in this directory. The comparison is on the parsed JSON *value*, not
   the byte string, so key order and whitespace don't matter. `expected.json` is written
   with sorted keys and 2-space indent purely for a stable diff; a conforming program may
   emit any equivalent JSON.

4. **On success: print exactly `OK <lang>` to stdout and exit 0** (for example
   `OK python`). The `<lang>` token must match the language name the orchestrator uses
   (`python`, `julia`, `csharp`, `r`, `clojure`). The orchestrator treats the `OK <lang>`
   marker as the success signal: a zero exit *without* the marker is still a `FAIL`.

5. **On failure: print a human-readable diff (expected vs actual) and exit non-zero.**

### Why a dedicated `expected.json` and not `fixtures/widget-state.json`?

The repo's main golden fixture (`fixtures/widget-state.json`) is a two-model *composition*
with binary buffers, deliberately exercising the hard serialization paths. The e2e
contract instead pins the **simplest possible** shape (one model, one scalar field, no
buffers) so a *new* language port can self-certify against it before it has implemented
buffer handling. The two fixtures are complementary: buffer and composition correctness
is still certified by each port's own test suite against `fixtures/widget-state.json`.

## The fixed input

```
model id: "counter"
state:
  _esm:  export default { render({ model, el }) { el.textContent = model.get("value"); } }
  value: 42
```

The Python reference builds it as:

```python
from cositos import dump_document

ESM = 'export default { render({ model, el }) { el.textContent = model.get("value"); } }'
doc = dump_document([("counter", {"_esm": ESM, "value": 42})])
```

`expected.json` in this directory is the canonical output of exactly that call.

## Adding a language

1. Write a standalone program that satisfies the contract above.
2. Add a `mise run e2e-<lang>` task that invokes it. The runtime it needs must be the one
   the orchestrator checks for (see `LANGUAGES` in `scripts/e2e_all.py`).
3. `mise run e2e-all` will pick it up automatically: `SKIP` where the runtime is absent,
   `OK` or `FAIL` where present.
