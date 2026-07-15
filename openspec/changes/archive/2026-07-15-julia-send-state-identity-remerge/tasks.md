## 1. Spec Update & Protocol Fix

- [x] 1.1 Add "Full State Send Includes Immutable Identity Fields" requirement to `openspec/specs/protocol/spec.md`
- [x] 1.2 Merge identity fields in Julia `send_state!` when `include === nothing` (mirror Python)
- [x] 1.3 Add regression test asserting identity fields present after full `send_state!`

## 2. Verify

- [x] 2.1 Run `mise run verify` (lint, typecheck, coverage, complexity, specs, coverage-audit)
- [x] 2.2 Run Julia host tests specifically to confirm new test passes