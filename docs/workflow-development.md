# Workflow development reference

Project-owned implementation details and validation history for this workflow repository. Start from [.lean/PROJECT.md](../.lean/PROJECT.md); the executable gate there remains authoritative. These notes do not prescribe downstream application structure or commands.

## Architecture

Bash scripts, Python 3.9+ standard-library tooling, JSON configuration and Markdown. No application, package manager, or build step.

- `AGENTS.md` canonical shared agent contract; `CLAUDE.md` runtime entrypoint importing it. The active agent owns this task; no provider-specific primary is imposed.
- `.lean/scripts/gate_evidence.py` binds review receipts to shipping state and records local control acceptance; neither proves independent authority.
- `.lean/scripts/gate_lock.py` holds a per-checkout gate lock across the shared runner; busy gates report NOT_RUN.
- `.lean/scripts/skill_effort.py` manages optional project-owned procedure preferences and routes active submodules to their record roots; no settings ship in the template.
- `.lean/scripts/quality-gate.sh` runs the PROJECT checks directly for Codex and through the Claude Stop adapter; direct calls always run without stdin or Claude cache state.
- `.lean/` the workflow: `policy/` rules (replaced on upgrade), `PROJECT.md` (project-owned), `CHANGELOG.md`, and `scripts/` + `tests/` self-checks.
- `.claude/` Claude runtime: `settings.json`, hooks (`quality-gate.sh` on `Stop`, `session-start.sh` on `SessionStart`, which records a change baseline without validating), skill discovery links, and a `reviewer` entrypoint for `.lean/roles/reviewer.md`.
- `.lean/skills/` contains nine core and ten optional procedures; discovery links expose only core by default (`skill_pack.py enable` adds extras). `.lean/config.json` ships unconfigured standard/direct; no task records are included. Mode tooling supports macOS/Linux/WSL through Unix fcntl.
- `.lean/scripts/submodule.py` installs/reuses remote application submodules under `targets/` and separates application roots from Lean-owned per-target record roots. Active selection is local/ignored; application gates run inside the target while mode tooling and model catalogs use target records.
- `.lean/scripts/clean_repo.py` provides read-only inventory, evidence-bearing plans and exact-ID cleanup with external snapshots/journaled recovery; no semantic unused-file inference or Git index writes. Tests use disposable repositories.
- `.lean/scripts/takeover.py` inventories a separate target, binds approved text operations to read coverage/source fingerprints, and journals apply/resume/rollback in a private external session. The shared takeover skill owns semantic migration and user decisions.
- `.github/` GitHub platform only: `workflows/lean-workflow.yml` runs the self-checks in CI when workflow files change; `pull_request_template.md`.

## Environment
Not defined. No application dependencies. Workflow tools require Bash, Git and Python 3.9+; native Windows is unsupported. `shellcheck` is used by the gate and CI (`brew install shellcheck` locally; preinstalled on `ubuntu-latest`). A container without it -- Claude Code on the web is one -- makes the gate report an environment problem rather than a failure, and the change stays unlinted until it is installed (`apt-get install -y shellcheck`, verified in that container).

## Test coverage
`.lean/tests/test-hooks.sh` tests the Quality Gate and SessionStart hooks (hook and onboarding checks in temporary repositories). Cases cover opt-in passing caches, baseline seeding, continued refusals, contract provenance and command failure classification. The gate's two verdicts are covered as a pair: a command the shell cannot find must be reported as an environment problem, and a command that exists and fails must not be -- including a wrapper that hands back another program's 127. Every term deciding that split is pinned on its own: remove the status test, either half of the command-name test, the resolve test or the assignment strip and a check fails.

Python tests: `python3 -m unittest discover -s .lean/tests -p 'test_*.py'` checks modes, claims, canonical routing and discovery-link integrity; `test_e2e.py` drives one standard -> tracker -> full -> standard lifecycle (claims, completion, clean-queue, downgrades) and fails if the lease, active-tracker or `--keep-pending` downgrade guard is removed; `test_guards.py` pins checklist variants, single-line tracker text and whitespace-padded agent ids. `python3 .lean/scripts/workflow.py check` validates the current mode.

Takeover tests in `test_takeover.py` exercise read-only inventory, read attestations, source/target/approval drift, dirty/untracked preservation, claim/path boundaries, interrupted apply/rollback and snapshot integrity in isolated repositories. Foreign-record tests additionally cover decision-bound mappings, original/evidence preservation, blocked/cancelled states, trusted staged validation and interrupted conversion recovery. APPLIED is deliberately distinct from semantic completion.

## Context selection evaluation

Use the [routing scenarios](../.lean/skills/lean-task/references/context-scenarios.md) when changing context selection. Record actual reads separately from expected results. Static instruction tests do not measure agent behavior, application correctness or token savings.
