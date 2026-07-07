"""Self-test for the reactive core's two claimed properties: glitch-freedom and cycle
detection. Run directly:  python examples/benchmarks/reactive_selftest.py

Not collected by pytest (lives under examples/); it is a standalone, runnable proof for
the benchmark's "reactive DAG" variant.
"""

from __future__ import annotations

from reactive import Computed, Effect, Signal


def test_diamond_recomputes_once() -> None:
    """S -> {D, E} -> C: setting S must recompute C exactly once (no glitch/double-fire)."""
    counter = {"n": 0}
    c_runs = {"n": 0}
    s = Signal(1, name="s")
    d = Computed(lambda: s.get() + 1, name="d", counter=counter)
    e = Computed(lambda: s.get() * 2, name="e", counter=counter)

    def c_fn() -> int:
        c_runs["n"] += 1
        return d.get() + e.get()

    c = Computed(c_fn, name="c", counter=counter)
    seen: list[int] = []
    Effect(lambda: seen.append(c.get()), name="obs", counter=counter)

    c_runs["n"] = 0  # ignore construction-time compute
    seen.clear()
    s.set(10)

    assert c_runs["n"] == 1, f"diamond glitched: C recomputed {c_runs['n']} times (expected 1)"
    assert seen == [10 + 1 + 10 * 2], f"stale value observed: {seen}"
    print("PASS: diamond recomputes exactly once (glitch-free)")


def test_cycle_raises() -> None:
    """A computed that (indirectly) reads itself must raise, not loop forever."""
    counter = {"n": 0}
    box: dict[str, Computed] = {}
    a = Computed(lambda: box["b"].get() + 1, name="a", counter=counter)
    b = Computed(lambda: box["a"].get() + 1, name="b", counter=counter)
    box["a"], box["b"] = a, b
    try:
        a.get()
    except RuntimeError as exc:
        assert "cycle" in str(exc)
        print(f"PASS: cycle detected and raised ({exc})")
        return
    raise AssertionError("expected RuntimeError on reactive cycle, none raised")


if __name__ == "__main__":
    test_diamond_recomputes_once()
    test_cycle_raises()
    print("all reactive self-tests passed")
