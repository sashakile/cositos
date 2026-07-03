set shell := ["bash", "-uc"]

default: test

test:
    uv run --extra dev pytest -q

lint:
    uv run --extra dev ruff check src tests

fmt:
    uv run --extra dev ruff format src tests

check:
    pretender check src
