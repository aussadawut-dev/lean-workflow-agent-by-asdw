# Project Context

This file describes repository-specific information for agents.

Update it as the project takes shape. "Not defined" is not an error: it means the repository has no convention here yet. Do not invent one; when work establishes a real convention, record it here.

## Purpose

Lean Workflow Baseline: a repository template with a shared Claude/Codex contract that gives a project a quality-driven coding workflow. It contains workflow files only, no application code. Current version: 4.1.0 (see `.lean/CHANGELOG.md`).

## Architecture

Bash scripts, Python 3.9+ standard-library tooling, JSON configuration and Markdown. No application, package manager, or build step.

- `AGENTS.md` canonical shared agent contract; `CLAUDE.md` runtime entrypoint importing it. The active agent owns this task; no provider-specific primary is imposed.
- `.lean/scripts/gate_evidence.py` binds review receipts to shipping state and records local control acceptance; neither proves independent authority.
- `.lean/scripts/quality-gate.sh` runs the PROJECT checks directly for Codex and through the Claude Stop adapter; direct calls always run without stdin or Claude cache state.
- `.lean/` the workflow: `policy/` rules (replaced on upgrade), `PROJECT.md` (project-owned), `CHANGELOG.md`, and `scripts/` + `tests/` self-checks.
- `.claude/` Claude runtime: `settings.json`, hooks (`quality-gate.sh` on `Stop`, `session-start.sh` on `SessionStart`, which records a change baseline without validating), skill discovery links, and a `reviewer` entrypoint for `.lean/roles/reviewer.md`.
- `.lean/skills/` contains eight core and seven optional maintenance procedures; discovery links expose only core by default (`skill_pack.py enable` adds extras). `.lean/config.json` ships unconfigured standard/direct; no task records are included. Mode tooling supports macOS/Linux/WSL through Unix fcntl.
- `.lean/scripts/submodule.py` installs/reuses remote application submodules under `targets/` and separates application roots from Lean-owned per-target record roots. Active selection is local/ignored; application gates run inside the target while mode tooling and model catalogs use target records.
- `.lean/scripts/clean_repo.py` provides read-only inventory, evidence-bearing plans and exact-ID cleanup with external snapshots/journaled recovery; no semantic unused-file inference or Git index writes. Tests use disposable repositories.
- `.lean/scripts/takeover.py` inventories a separate target, binds approved text operations to read coverage/source fingerprints, and journals apply/resume/rollback in a private external session. The shared takeover skill owns semantic migration and user decisions.
- `.github/` GitHub platform only: `workflows/lean-workflow.yml` runs the self-checks in CI when workflow files change; `pull_request_template.md`.

## Commands

### Install
Not defined. No application dependencies. Workflow tools require Bash, Git and Python 3.9+; native Windows is unsupported. `shellcheck` is used by the gate and CI (`brew install shellcheck` locally; preinstalled on `ubuntu-latest`). A container without it -- Claude Code on the web is one -- makes the gate report an environment problem rather than a failure, and the change stays unlinted until it is installed (`apt-get install -y shellcheck`, verified in that container).

### Build
Not defined.

### Test
`.lean/tests/test-hooks.sh` tests the Quality Gate and SessionStart hooks (hook and onboarding checks in temporary repositories). Cases cover opt-in passing caches, baseline seeding, continued refusals, contract provenance and command failure classification. The gate's two verdicts are covered as a pair: a command the shell cannot find must be reported as an environment problem, and a command that exists and fails must not be -- including a wrapper that hands back another program's 127. Every term deciding that split is pinned on its own: remove the status test, either half of the command-name test, the resolve test or the assignment strip and a check fails.

Python tests: `python3 -m unittest discover -s .lean/tests -p 'test_*.py'` checks modes, claims, canonical routing and discovery-link integrity; `test_e2e.py` drives one standard -> tracker -> full -> standard lifecycle (claims, completion, clean-queue, downgrades) and fails if the lease, active-tracker or `--keep-pending` downgrade guard is removed; `test_guards.py` pins checklist variants, single-line tracker text and whitespace-padded agent ids. `python3 .lean/scripts/workflow.py check` validates the current mode.

Takeover tests in `test_takeover.py` exercise read-only inventory, read attestations, source/target/approval drift, dirty/untracked preservation, claim/path boundaries, interrupted apply/rollback and snapshot integrity in isolated repositories. Foreign-record tests additionally cover decision-bound mappings, original/evidence preservation, blocked/cancelled states, trusted staged validation and interrupted conversion recovery. APPLIED is deliberately distinct from semantic completion.

### Lint
`shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh` (0.11.0; passes at default severity, same as CI).
`.lean/scripts/check-structure.sh` checks referenced paths, retired paths, settings, hook executability, frontmatter, `.gitignore` entries for the gate's state files, and `PROJECT.md` gate markers (~0.3s). Verified: passes, exits non-zero on failure.

### Typecheck
Not defined.

### Quality Gate

The turn gate runs hook/discovery integrity checks below. The full Python suite remains required before shipping workflow behavior changes and runs in CI; execute `python3 -m unittest discover -s .lean/tests -p 'test_*.py'` before review. Keeping this broad suite out of every Stop reduces turn latency without substituting smoke checks for release validation.

Commands run explicitly by Codex and by the Claude `Stop` hook (`.claude/hooks/quality-gate.sh`) before a turn can finish. One command per line, fast checks first. Each must exit non-zero on failure (e.g. `command -v gofmt >/dev/null && output=$(gofmt -l .) && test -z "$output"`, not a formatter that merely prints errors or a substitution masking a missing tool). Missing or empty checks block with an undefined-gate message. Add verified project commands during onboarding. Local gate-control changes require an already approved acceptance record (see policy/QUALITY.md).

<!-- gate:start -->
```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-hooks.sh
python3 .lean/scripts/workflow.py --root . check
python3 .lean/scripts/model_catalog.py --root . check
python3 -m unittest discover -s .lean/tests -p 'test_gate_integrity.py'
python3 -m unittest discover -s .lean/tests -p 'test_skill_pack.py'
```
<!-- gate:end -->

## Important paths

- `CLAUDE.md`, `AGENTS.md` agent contract
- `.lean/policy/` workflow rules (do not edit per project)
- `.claude/hooks/` gate and session hooks
- `.lean/scripts/`, `.lean/tests/` self-checks for the workflow files

## High-risk areas

- `.claude/hooks/` and `.claude/settings.json`: run on every turn and control permissions; a bug can block all work or widen access.
- `.lean/policy/`: changes alter behavior for every downstream project on upgrade.

## Documentation routes

- `README.md` template usage, layout, checks
- `.lean/CUSTOMIZING.md` imports, current authority and upgrades
- `.lean/README.md` policy router
- `.lean/CHANGELOG.md` versions and upgrade steps
- `CONTRIBUTING.md` how to change the workflow files
