## 1. Buffer-Split Edge Cases (protocol spec)

- [x] 1.1 Add cycle detection to Julia's `_separate` in `julia/src/Cositos.jl` (currently missing — Python has it via `ancestors` tuple, Julia doesn't)
- [x] 1.2 Add depth capping to Julia's `_separate` in `julia/src/Cositos.jl` (currently missing — Python has it via `_MAX_DEPTH`)
- [x] 1.3 Add cycle detection and depth capping to C#'s `Separate` in `csharp/Core.cs` (currently missing)
- [x] 1.4 Add cycle detection and depth capping to Clojure's `separate` in `clojure/src/cositos/core.clj` (currently missing)
- [x] 1.5 Add cycle detection and depth capping to R's `separate` in `r/core.R` (currently missing)
- [x] 1.6 Create code-based test cases in each language's test suite for cycle detection and depth capping (JSON fixtures cannot represent cyclic references)
- [x] 1.7 Update each language's fixture-certification test to assert cycle and depth errors (not just happy-path)

## 2. Lifecycle Reducer — Python (lifecycle spec, design D1–D6)

- [x] 2.1 Define the effect data types in `src/cositos/lifecycle.py`: `Send`, `Listen`, `ApplyState`, `InvokeCustom`, `Error` as frozen dataclasses with a `kind` discriminator
- [x] 2.2 Define the event data types in `src/cositos/lifecycle.py`: `Open`, `SendState`, `SendCustom`, `Inbound`, `Close`, `CommIdAssigned` as frozen dataclasses
- [x] 2.3 Define the phase enum: `Phase.UNOPENED`, `Phase.OPEN`, `Phase.CLOSED`
- [x] 2.4 Define the `TransportCapabilities` dataclass with `supports_receive`, `supports_request_state`, `supports_custom`, `supports_buffers` (all default `True`)
- [x] 2.5 Implement `reduce(phase, event, current_state, capabilities) → (new_phase, effects)` as a pure function with explicit branches for every (phase, event) pair
- [x] 2.6 Write fixture JSON files in `fixtures/lifecycle/`: one per event type (open, full-send, filtered-send, inbound-update, inbound-request-state, inbound-custom, inbound-unknown, close, comm-id-assigned, one-way-open)
- [x] 2.7 Write `tests/test_lifecycle.py` — load every fixture, call `reduce`, assert exact output, no kernel/transport/mocking needed

## 3. Imperative Shell — Python (lifecycle-shell spec, design D7)

- [x] 3.1 Implement `WidgetShell` in `src/cositos/lifecycle.py` (or a new `shell.py`): stores `(phase, capabilities)`, calls `reduce`, walks effects, delegates to transport/host callbacks
- [x] 3.2 Implement public API methods: `open()`, `send_state(include)`, `send_custom(content, buffers)`, `close()`, `mimebundle()`, `_repr_mimebundle_()` — same signatures as current `Widget`
- [x] 3.3 Wire the inbound callback loop: `on_message` feeds inbound data through `parse_message` and `put_buffers`, then back into `reduce` as `Inbound` events
- [x] 3.4 Implement the comm-id feedback loop: after executing a `send("comm_open")` effect, read `transport.comm_id()` and feed `CommIdAssigned` back into `reduce`
- [x] 3.5 Write `tests/test_shell.py` — parity tests against the existing `test_model.py` using the same `FakeTransport`, verifying identical behavior

## 4. Replace Existing Widget — Python

- [x] 4.1 Replace `Widget` class internals in `src/cositos/model.py` to delegate to `WidgetShell` (public API unchanged)
- [x] 4.2 Run full test suite: `python -m pytest tests/test_model.py tests/test_lifecycle.py tests/test_shell.py` — all pass
- [ ] 4.3 Run e2e tests: `python -m pytest tests/test_e2e_jupyter.py` — widget still renders and interacts live

## 5. Lifecycle Reducer — Julia

- [ ] 5.1 Define effect and event types in `julia/src/Cositos.jl` (as structs with a `kind` symbol, or plain `Dict` — Julia idiom)
- [ ] 5.2 Implement `reduce(phase, event, current_state, capabilities) → (new_phase, effects)` in `julia/src/Cositos.jl`
- [ ] 5.3 Load and certify against `fixtures/lifecycle/*.json` in Julia's test runner
- [ ] 5.4 Implement `WidgetShell` replacing the current lifecycle code in `Cositos.jl` (lines ~383-475 of the `Widget` mutable struct)
- [ ] 5.5 Run existing `host_tests.jl` — all pass without modification
- [ ] 5.6 Run e2e parity test: `julia/test/runtests.jl`

## 6. Lifecycle Shell — C# and R

- [ ] 6.1 Implement `reduce` function in `csharp/Core.cs` (currently no lifecycle code at all)
- [ ] 6.2 Certify C# reducer against `fixtures/lifecycle/*.json`
- [ ] 6.3 Implement C# imperative shell (Widget wrapper around the reducer)
- [ ] 6.4 Implement `reduce` function in `r/core.R` (currently no lifecycle code at all)
- [ ] 6.5 Certify R reducer against `fixtures/lifecycle/*.json`
- [ ] 6.6 Implement R imperative shell (Widget wrapper around the reducer)

## 7. Capability Flags and Clojure Documentation (design D5)

- [ ] 7.1 Define `TransportCapabilities` struct for Julia, generalizing the single `supports_receive` flag (Python already covered in task 2.4)
- [ ] 7.2 Update `PythonJupyter.CommTransport` (and Julia's `IJuliaCommTransport`) to declare full capabilities
- [ ] 7.3 Add a comment / docstring to Clojure's `clojupyter_transport.clj` explicitly listing which capability flags are `False` (no buffers, no custom, no request_state)
- [ ] 7.4 Update the clojupyter-transport section in `docs/porting.md` to reference the capability flags and explain which events the Clojure path cannot handle

## 8. Documentation

- [ ] 8.1 Write the lifecycle fixtures section in `fixtures/README.md` explaining the fixture format for `fixtures/lifecycle/*.json`
- [ ] 8.2 Update `docs/porting.md`: add **Step 5 — Widget Lifecycle** after the existing four steps, explaining the reducer contract and pointing to `fixtures/lifecycle/`
- [ ] 8.3 Update `docs/reference/api-cheatsheet.qmd` with new symbols: `reduce`, effect types, event types, phase enum, `TransportCapabilities`
- [ ] 8.4 Update the `protocol` spec in `openspec/specs/protocol/spec.md` to include the cycle-detection and depth-cap requirements from the delta spec (sync after archive)

## 9. Verification

- [ ] 9.1 Run all existing examples (`examples/benchmarks/`, `examples/dashboard/`, `examples/e2e/`) against the shell-based Widget to confirm no regressions (the "no breaking changes" claim)
- [ ] 9.2 Run full test suite across all languages after Widget replacement: `mise run verify`