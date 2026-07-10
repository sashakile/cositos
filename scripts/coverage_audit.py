#!/usr/bin/env python3
"""Coverage-manifest audit — enforcement gate E1 (see TOOL_EVALUATION.md, F19).

Fails the build when quality-tool coverage silently drifts:

  1. A backend directory exists on disk but is not declared in coverage-manifest.toml.
  2. A directory declares `pretender = true` but `pretender check <dir>` parses zero
     files (i.e. the coverage is a silent no-op — the F19 failure mode).

Every declared directory must carry either a tool binding (pretender/espectacular) or
an explicit `exempt = "<reason>"`. Adding a new backend language therefore *forces* a
reviewed coverage decision instead of quietly going unchecked.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "coverage-manifest.toml"

# Top-level dirs that are never backend cores (infra/tooling/tests/docs).
NON_CORE = {
    "docs", "examples", "tests", "fixtures", "openspec", "front", "scripts",
    "node_modules", "target",
}


def _is_gitignored(path: Path) -> bool:
    """True iff `path` is fully excluded by .gitignore (e.g. local-only scratch dirs
    like `handoffs/`, see TOOL_EVALUATION.md F32). Never raises on a missing/broken git
    binary — treated as "not ignored" so the audit still runs (fails safe, not silent).
    """
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", str(path)], cwd=ROOT, capture_output=True,
        )
    except OSError:
        return False
    return proc.returncode == 0


def discover_backend_dirs() -> set[str]:
    """Top-level code directories that ought to be covered.

    `front` is excluded here because its code lives at `front/src`, which the manifest
    tracks by that nested key. Gitignored directories (local-only artifacts, never part
    of the shipped source tree — e.g. the `create-handoff` skill's `handoffs/`) are
    skipped too: they are not backend cores, and flagging them blocks unrelated commits
    (F32).
    """
    found: set[str] = set()
    for entry in ROOT.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if entry.name in NON_CORE:
            continue
        if _is_gitignored(entry):
            continue
        found.add(entry.name)
    return found


def pretender_parses_files(rel: str) -> bool | None:
    """True iff `pretender check <rel>` parses at least one file.
    Returns None if `pretender` binary is not installed (e.g. in CI).
    """
    try:
        proc = subprocess.run(
            ["pretender", "check", rel, "--format", "json"],
            cwd=ROOT, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return False
    return len(payload.get("files", [])) > 0


def main() -> int:
    if not MANIFEST.exists():
        print(f"coverage-audit: missing {MANIFEST.name}", file=sys.stderr)
        return 1

    manifest = tomllib.loads(MANIFEST.read_text())
    cores: dict[str, dict] = manifest.get("cores", {})
    declared = set(cores.keys())

    errors: list[str] = []

    # (1) undeclared backend directories
    for name in sorted(discover_backend_dirs() - {d.split("/")[0] for d in declared}):
        errors.append(
            f"backend dir '{name}/' is not declared in coverage-manifest.toml — add a "
            f"pretender/espectacular binding or an explicit exempt reason."
        )

    # (2) declared dirs: must have a binding or an exemption; pretender bindings must
    #     actually parse files.
    for name, cfg in sorted(cores.items()):
        path = ROOT / name
        if not path.exists():
            errors.append(f"declared dir '{name}/' does not exist on disk (stale manifest entry).")
            continue
        has_binding = cfg.get("pretender") or cfg.get("espectacular")
        if not has_binding and "exempt" not in cfg:
            errors.append(f"'{name}/' has no tool binding and no exempt reason.")
        if cfg.get("pretender"):
            result = pretender_parses_files(name)
            if result is None:
                print(f"  ⚠ '{name}/' claims pretender=true but `pretender` binary not found (CI gap, see cositos-dad.19)")
            elif not result:
                errors.append(
                    f"'{name}/' claims pretender=true but `pretender check {name}` parses 0 "
                    f"files — coverage is a silent no-op (F19)."
                )

    if errors:
        print("coverage-audit FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        return 1

    print(f"coverage-audit OK: {len(cores)} directories declared and consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
