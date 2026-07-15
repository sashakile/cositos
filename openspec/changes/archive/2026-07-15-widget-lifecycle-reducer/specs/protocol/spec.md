## ADDED Requirements

### Requirement: Buffer-Split Algorithm Detects Cycles
The system SHALL detect cyclic references in widget state during `remove_buffers` and raise a clear error rather than infinite-looping or stack-overflowing.

#### Scenario: Cyclic state raises a clear error
- **GIVEN** a state dict that contains a reference to itself (a cycle: `substate appears in its own ancestor chain`)
- **WHEN** `remove_buffers` is called on that state
- **THEN** a `ValueError` SHALL be raised (or language-equivalent) naming the path where the cycle was detected
- **AND** the interpreter SHALL NOT overflow its call stack

#### Scenario: Shared but acyclic subtrees (DAG) are fine
- **GIVEN** a state dict where two branches point to the same child dict (shared reference, not a cycle)
- **WHEN** `remove_buffers` is called
- **THEN** it SHALL complete without error
- **AND** the stripped output SHALL contain two copies of the child (since the wire format is a tree)

### Requirement: Buffer-Split Algorithm Caps Nesting Depth
The system SHALL cap container nesting depth during `remove_buffers` at a fixed maximum and raise a clear error when exceeded, rather than stack-overflowing.

#### Scenario: State exceeding max depth raises a clear error
- **GIVEN** a state dict whose container nesting depth exceeds the implementation-defined maximum (e.g., 500 levels)
- **WHEN** `remove_buffers` is called
- **THEN** a `ValueError` SHALL be raised (or language-equivalent) naming the path where the limit was exceeded
- **AND** the error SHALL be distinguishable from a raw `RecursionError`

#### Scenario: Shallow state passes through normally
- **GIVEN** a state dict with typical nesting depth (less than the limit)
- **WHEN** `remove_buffers` is called
- **THEN** it SHALL complete normally with no depth-related errors

### Requirement: Fixtures Cover Buffer-Split Edge Cases
The system SHALL provide test coverage for cycle-detection and depth-cap requirements in each language's test suite, since cyclic state cannot be represented in JSON.

#### Scenario: Cycle test case exists in each language's test suite
- **WHEN** checking each port's test suite (`tests/test_buffers.py`, `julia/test/host_tests.jl`, etc.)
- **THEN** there SHALL be a test case that constructs a cyclic state (a dict containing a reference to an ancestor), calls `remove_buffers`, and asserts the expected cycle error
- **AND** the test SHALL use programmatic construction since JSON cannot express pointer identity

#### Scenario: Deep-nesting fixture exists
- **WHEN** checking the fixture set
- **THEN** there SHALL be a code-based test case in each language's test suite whose state nesting exceeds the cap, calling `remove_buffers`, and asserting the expected depth-limit error