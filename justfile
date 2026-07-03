set shell := ["bash", "-uc"]

default: verify

# --- Python (core) ---
test:
    uv run --extra dev --extra oracle pytest

lint:
    uv run --extra dev ruff check src tests

fmt:
    uv run --extra dev ruff format src tests

typecheck:
    uv run --extra dev mypy

coverage: test   # pytest config enforces --cov-fail-under

# --- JS (front) ---
front-test:
    cd front && node --test

front-typecheck:
    cd front && npx tsc --noEmit

front-coverage:
    cd front && npm run coverage

# --- Cross-cutting quality gates (also run in the git hook) ---
complexity:
    pretender check src front/src

specs:
    ah check

# Full local gate: lint, typecheck, coverage (py+js), complexity, specs.
verify: lint typecheck coverage front-typecheck front-coverage complexity specs
    @echo "✅ all cositos quality gates passed"
