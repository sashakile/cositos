# How bd/Dolt remote sync works

Research for `cositos-dad.9`, gathered 2026-07-07 against `bd version 1.1.0
(Homebrew)`. Evidence: `docs/core-concepts/sync-concepts.md` from
[gastownhall/beads](https://github.com/gastownhall/beads/blob/main/docs/core-concepts/sync-concepts.md)
plus local `bd dolt --help`, `bd bootstrap --help`, `bd merge-slot --help`,
`bd gc --help`, and `bd dolt show` run against this repo.

## What refs/dolt/data actually stores

Beads issue data lives in an embedded Dolt database (`.beads/embeddeddolt` in
this repo—confirmed via `bd dolt show`), not in git-tracked files. The local
Dolt database, not `.beads/issues.jsonl`, is the source of truth for every
`bd` read/write command.

Cross-machine sync uses **Dolt remotes**, which for a normal git-hosted
project can be the *same* `origin` URL as the source code. Dolt stores issue
history under `refs/dolt/data`, a ref namespace separate from `refs/heads/main`
and any other source branch. Pushing/pulling issue history is entirely
decoupled from pushing/pulling source code—a `git push` doesn't sync
issues, and `bd dolt push` doesn't touch source branches.

`.beads/issues.jsonl` is an **export only**—for viewers, interchange,
migration, and backup. It's not the sync channel. Critically: `bd import
.beads/issues.jsonl` is upsert-only and can't infer deletions, so routine
sync must never use it as a substitute for `bd dolt pull`.

## How bd sync push/pull actually work

```bash
bd dolt push              # push local Dolt commits to the configured remote
bd dolt pull               # pull commits from the configured remote
bd dolt push --force       # overwrite remote changes (e.g. remote has uncommitted working-set changes)
bd dolt pull --remote foo  # pull from a specific named remote instead of the default
```

Setup path (see below) automatically detects `git remote get-url origin` on `bd init`
and configures a Dolt remote also named `origin`—so on a fresh repo, no
extra remote configuration step is normally needed once a git remote exists
*before* `bd init` runs. This repo's `bd init` already happened with no git
remote, so that automatic origin detection never fired (see Setup section).

## What a Dolt merge conflict looks like, and how it's resolved

The beads docs don't describe an automatic three-way-merge conflict UI for
`bd dolt pull`—bd's design instead prevents concurrent-write races
procedurally, via the **merge-slot gate**:

- Each rig (repo) has one merge-slot bead (`<prefix>-merge-slot`, labeled
  `gt:slot`) that acts as an exclusive-access primitive.
- `bd merge-slot acquire` / `check` / `release`—only one agent holds the
  slot at a time, serializing who is allowed to resolve conflicts and push.
- The stated purpose, verbatim from `bd merge-slot --help`, is preventing
  "monkey knife fights where multiple polecats race to resolve conflicts and
  create cascading conflicts."

If a real Dolt-level conflict does occur despite that (for example, a bypassed slot,
a stale clone), the repair path is `bd doctor --check=validate --fix`—one
of `bd doctor`'s named checks explicitly covers "git conflicts" as part of
data-integrity validation, alongside duplicate and orphaned-dependency
repair.

**Practical implication for cositos:** once agents/contributors run in
parallel here, adopt the merge-slot convention (`bd merge-slot create` once,
then `acquire`/`release` around any `bd dolt push`) rather than assuming Dolt
will silently merge concurrent issue edits.

## Anti-patterns the docs warn against

1. **Don't use `bd import .beads/issues.jsonl` as routine sync.** It's
   upsert-only; it can't detect that a record missing from the export was
   deleted upstream, so periodic re-import can resurrect closed/deleted
   issues.
2. **Don't treat JSONL automatic export as a backup or sync mechanism.**
   `export.auto` (off by default) only keeps `.beads/issues.jsonl` fresh for
   viewers/interchange; cross-machine sync and backups are Dolt remotes and
   `backup.*` config, never JSONL.
3. **Post-merge/post-checkout JSONL import is a compatibility fallback
   only** for old projects with no Dolt remote configured (`sync.remote`
   unset)—it prints a warning that this path is "not durable sync." A
   project with `sync.remote` configured skips this fallback entirely.
4. **`bd dolt push --force` overwrites remote history**—only use it
   knowingly (for example, remote has stray uncommitted working-set changes), not as
   a routine "push failed, just force it" reflex.

## Exact commands required after a remote is added (setup, not usage)

This repo currently has **no git remote** (`git remote -v` is empty) and `bd
dolt show` confirms `Remotes: (none)`. Once `cositos-dad.14` (decide target
remote) and `cositos-dad.11` (add remote + push) are done, the Dolt side needs
its own explicit setup—`bd init` already ran without a git remote present,
so the automatic remote wiring never happened:

```bash
# 1. Confirm no stale Dolt remote config
bd dolt remote list

# 2. Optional safety export before wiring remotes
bd export -o .beads/issues.pre-remote.jsonl

# 3. Add the Dolt remote—same URL as the git origin just added
bd dolt remote add origin <git-origin-url>
# Dolt-compatible URL forms: git+ssh://git@github.com/org/repo.git
#                          or git+https://github.com/org/repo.git

# 4. First publish of issue history
bd dolt push

# 5. Confirm sync.remote is persisted to .beads/config.yaml, then commit it
git add .beads/config.yaml
git commit -m "chore(beads): wire Dolt remote after publish"
```

Any other machine/contributor/agent clone afterward runs:

```bash
bd bootstrap        # automatically detects refs/dolt/data on git origin, clones Dolt history,
                     # and wires that origin as the Dolt remote for future push/pull
# or, if a local database already exists and is just stale:
bd dolt pull
```

`bd bootstrap --dry-run` is available to preview the plan first (also
`--json` for scripting)—worth running once by hand before trusting it in an
agent's autonomous startup sequence.

## Adjacent lifecycle commands worth knowing before advertising this widely

Not part of sync itself, but directly relevant once multiple contributors are
generating issue history:

- `bd compact --dry-run` / `--force`—squash Dolt commits older than N days
  (default 30), keeps recent history via cherry-pick. Reduces storage
  overhead from automatic-commit churn.
- `bd flatten`—"nuclear option," squashes *all* Dolt history into one
  commit. Irreversible; only for when commit-level time-travel isn't needed.
- `bd gc`—full lifecycle GC: decay old closed issues (default 90 days) +
  compact + Dolt GC. Has `--dry-run`.

These map onto the exact category of problem `cositos-dad.1`/`cositos-dad.10`
are wrestling with for `.dont`'s plain git-tracked `db.cozo`—Dolt's answer
to "a database that grows forever in git history" is dedicated compaction
tooling, not just gitignoring the working state. Worth revisiting in
`cositos-dad.10`'s design (see next section).

## Feeds into cositos-dad.10 (.dont sync design)

Key transferable shape, for whoever picks up `cositos-dad.10`:

- Dolt's sync model is **push/pull of a separate, dedicated ref
  (`refs/dolt/data`)** decoupled from the main branch—not "commit the
  binary DB to the working tree and let normal git diffs carry it," which is
  what `.dont/db.cozo` currently does (`cositos-dad.1`).
- Dolt ships purpose-built compaction (`bd compact`/`bd flatten`/`bd gc`)
  *because* a growing embedded database in version control is a known,
  anticipated problem—not something to solve by disabling versioning
  entirely.
- If `dont` has no equivalent remote/ref mechanism, the honest fallback is
  the same one beads used to reach for before Dolt: gitignore the local
  database entirely (mirrors `.beads/`'s exclusion) and accept that `dont`
  claims are local-only until/unless it grows an equivalent sync primitive.
