# Migrating from 4.x to 5.0.0

[Back to README](../README.md)

5.0.0 keeps the workflow (contracts, guard, gate, receipts, modes, trackers, queue, review rules) and changes how it is packaged. Project records stay as they are.

## What moved

| 4.x | 5.0.0 |
|---|---|
| `python3 .lean/scripts/workflow.py configure\|show\|check\|context\|downgrade` | `python3 .lean/bin/lean mode configure\|show\|check\|context\|downgrade` |
| `workflow.py tracker ...`, `workflow.py queue ...` | `lean tracker ...`, `lean queue ...` |
| `contract_guard.py declare --contract '...'` | `lean contract declare --contract '...'` |
| `bash .lean/scripts/quality-gate.sh [--cache-tree] [--contract] [--require-review]` | `lean gate run [same options]` |
| `gate_evidence.py state\|record-review\|check-review\|accept-controls` | `lean evidence state\|record-review\|check-review`, `lean gate accept-controls` |
| `gate_mode.py [mode]`, `.codex/quality-gate.json` | `lean gate mode [mode]`, `.lean/gate.json` |
| `skill_effort.py [level] [skill]` | `lean effort [level] [skill]` |
| `.lean/scripts/check-structure.sh`, ShellCheck | `lean lint` |
| `python3 -m unittest discover -s .lean/tests`, `run_tests.py` | `lean test --changed` (everyday), `lean test --all` (CI, release) |
| `tools/check_commit_attribution.py` | `lean attribution` |
| `submodule.py use\|context\|clear\|gate` | `lean target use\|context\|clear\|gate` (records stay in `.lean/targets/<name>/`) |
| `model_catalog.py`, `model_drift.py`, `.lean/model-catalog.json` | `lean models [check --live]`, `.lean/models.json` |
| `.claude/hooks/*.sh`, `.codex/hooks/quality_gate.py` | `lean hook claude\|codex <event>` |
| `.claude/.gate-cache`, `.claude/.gate-failed` | `.agent-runtime/gate-cache`, `.agent-runtime/gate-failed` |

## What was removed

The optional skills `lean-audit`, `lean-catalog`, `lean-compress`, `lean-pattern`, `lean-playbook`, `lean-prune` and `lean-takeover`, the optional skill pack (`skill_pack.py`) and queue cleanup (`clean-queue`). Existing `.agents/queue/history/` stays readable. `lean-target` stays as a core skill: application targets and their records in `.lean/targets/<name>/` keep working, and the active selection in `.agent-runtime/active-target.json` carries over. Projects that relied on a removed skill can keep the 4.x copy as a local project skill.

## What changed in behavior

- Spawning: without `/lean-agents`, at most `max_agents` (1) sized agent runs at a time. `/lean-agents` alone now spawns as many agents as the work has parallel tasks; `/lean-agents <model> xN` runs up to N at once on that model. 4.x required explicit intent for any parallel worker.
- Tests in the gate run by impact (`lean test --changed`); the full suite moves to CI and releases.
- Progress bars appear in replies and every runtime surface.

## Steps

1. Finish or pause running work: no active claims, no `lean spawn run` agents, trackers synchronized.
2. Fetch the pinned release and preview from it (4.x has no `lean` command):
   ```sh
   git clone --branch v5.0.0 https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git /tmp/lean-5
   python3 /tmp/lean-5/.lean/bin/lean update preview --target /path/to/project --ref v5.0.0
   ```
   The preview writes nothing to the project. It lists files to write, delete (retired 4.x files), merge (`AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `.codex/hooks.json`: only Lean's own hook entries are replaced) and migrate (gate block commands, `.codex/quality-gate.json`, skill links).
3. Review the plan, then apply it: `python3 /tmp/lean-5/.lean/bin/lean update apply --workspace <workspace>`. Keep the workspace: `lean update rollback --workspace <workspace>` restores the snapshot.
4. In the project: `python3 .lean/bin/lean lint`, `lean --root . mode check`, `lean gate run`. Update any project text (AGENTS.md additions, PROJECT.md) that still names a 4.x script; the preview lists them and lint reports them. The gate will refuse the changed controls until an independent HIGH review covers the update or you record your approval with `lean gate accept-controls --reason '<approval>'`.
5. Start a new agent session so hooks load from the new configuration.
