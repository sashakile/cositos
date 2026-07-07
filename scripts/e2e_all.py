#!/usr/bin/env python3
"""``mise run e2e-all`` — cross-language e2e orchestrator (cositos-1wi.1).

Runs every per-language e2e example (see ``examples/e2e/README.md`` for the shared
contract) in **isolation** and prints a per-language OK / SKIP / FAIL summary. It exists
so cross-backend verification is decoupled from the fragile Quarto docs render
(``polyglot-parity.qmd`` aborts the whole build on any divergence): one command proves
all backends work and degrades gracefully per language.

Classification, per language:

  * runtime binary not on PATH        -> SKIP (``no <runtime>``)   — not a failure
  * per-language mise task not defined -> SKIP (transitional: the per-language ticket
                                                that implements ``e2e-<lang>`` has not
                                                landed yet)
  * task runs, exits 0, prints ``OK <lang>`` -> OK
  * anything else (non-zero exit, or a zero exit without the ``OK <lang>`` marker) -> FAIL

The process exits non-zero **iff** at least one language FAILed. A SKIP never fails the
run, so a machine missing (say) Julia or .NET still certifies every backend it *can*.

The orchestration core (:func:`orchestrate`) takes injectable ``which`` / ``task_exists``
/ ``run_task`` callables so it is unit-testable without any real runtime; :func:`main`
wires the real implementations (``shutil.which`` and ``mise``).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

# How much of a failing program's output to surface in the summary detail.
_DETAIL_CHARS = 500


class Outcome(Enum):
    OK = "OK"
    SKIP = "SKIP"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Language:
    """A backend language and how to run its e2e example."""

    name: str  # contract name, e.g. "python" (matches the "OK <name>" marker)
    runtime: str  # binary that must be on PATH, e.g. "julia"
    task: str  # mise task that runs the example, e.g. "e2e-python"


@dataclass(frozen=True)
class Result:
    language: str
    outcome: Outcome
    detail: str  # skip reason, or the tail of a failing run's output


# The per-language examples the orchestrator drives. Each ``task`` is implemented by its
# own ticket (cositos-1wi.2..6); until then the task is absent and the language SKIPs.
LANGUAGES: tuple[Language, ...] = (
    Language("python", "uv", "e2e-python"),
    Language("julia", "julia", "e2e-julia"),
    Language("csharp", "dotnet", "e2e-csharp"),
    Language("r", "Rscript", "e2e-r"),
    Language("clojure", "clojure", "e2e-clojure"),
)

WhichFn = Callable[[str], str | None]
TaskExistsFn = Callable[[str], bool]
RunTaskFn = Callable[[str], tuple[int, str]]


def run_language(
    lang: Language,
    *,
    which: WhichFn,
    task_exists: TaskExistsFn,
    run_task: RunTaskFn,
) -> Result:
    """Classify a single language's e2e run. See the module docstring for the rules."""
    if which(lang.runtime) is None:
        return Result(lang.name, Outcome.SKIP, f"no {lang.runtime}")
    if not task_exists(lang.task):
        return Result(lang.name, Outcome.SKIP, f"{lang.task} not implemented yet")

    returncode, output = run_task(lang.task)
    if returncode == 0 and f"OK {lang.name}" in output:
        return Result(lang.name, Outcome.OK, "")
    return Result(lang.name, Outcome.FAIL, output.strip()[-_DETAIL_CHARS:])


def orchestrate(
    languages: Sequence[Language],
    *,
    which: WhichFn,
    task_exists: TaskExistsFn,
    run_task: RunTaskFn,
) -> tuple[list[Result], int]:
    """Run every language in isolation. Returns (results, exit_code).

    ``exit_code`` is non-zero iff at least one language FAILed; a FAIL in one language
    never stops the others from running.
    """
    results = [
        run_language(lang, which=which, task_exists=task_exists, run_task=run_task)
        for lang in languages
    ]
    exit_code = 1 if any(r.outcome is Outcome.FAIL for r in results) else 0
    return results, exit_code


def format_summary(results: Sequence[Result]) -> str:
    """Render the per-language OK/SKIP/FAIL table."""
    width = max((len(r.language) for r in results), default=4)
    lines = ["", "e2e-all summary:", "-" * (width + 12)]
    for r in results:
        suffix = f"  ({r.detail})" if r.detail else ""
        lines.append(f"  {r.language.ljust(width)}  {r.outcome.value}{suffix}")
    counts = {o: sum(1 for r in results if r.outcome is o) for o in Outcome}
    lines.append(
        f"-> {counts[Outcome.OK]} OK, {counts[Outcome.SKIP]} SKIP, {counts[Outcome.FAIL]} FAIL"
    )
    return "\n".join(lines)


def _defined_tasks() -> set[str]:
    """Names of tasks currently defined in mise (so absent ones SKIP, not error)."""
    proc = subprocess.run(
        ["mise", "tasks", "ls", "--json"], capture_output=True, text=True, check=True
    )
    return {t["name"] for t in json.loads(proc.stdout)}


def _run_mise_task(task: str) -> tuple[int, str]:
    proc = subprocess.run(["mise", "run", task], capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    defined = _defined_tasks()
    results, exit_code = orchestrate(
        LANGUAGES,
        which=shutil.which,
        task_exists=lambda t: t in defined,
        run_task=_run_mise_task,
    )
    print(format_summary(results))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
