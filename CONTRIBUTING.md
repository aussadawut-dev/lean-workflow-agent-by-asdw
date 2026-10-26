# Contributing

Thanks for taking a look. This repository is the workflow template, and changes can reach projects that copy it. Keep changes portable, clear and backed by evidence.

Start with `AGENTS.md` and `.lean/README.md`. When instructions change, update the canonical contract and shared procedures together. Skill bodies live in `.lean/skills/`; keep the ten discovery links for Claude (`.claude/skills/`) and Codex (`.agents/skills/`). Code lives in `.lean/lean/`, standard library only. Keep actual trackers, queue items, credentials and runtime state out of the template.

## Check the change

Run deterministic checks before review:

```sh
python3 .lean/bin/lean gate run
python3 .lean/bin/lean test --all   # the full suite, as CI runs it
```

The gate runs the commands in `.lean/PROJECT.md`: lint, mode and model-list checks, the attribution check and the tests the change can affect. Tests use temporary repositories so the template stays free of task records. New tests go in `.lean/tests/{unit,hooks,e2e}/`, with a rule in `.lean/tests/impact.json` and an entry in `.lean/assets.json` ([development guide](docs/development.md)).

Behavior changes need meaningful tests. For a bug fix, show its regression test failing before the fix and passing afterward. Review after validation; HIGH-depth work needs an independent reviewer. Every feature needs to work for Claude, Codex and agy, or record the provider gap in its documentation and tests.

For public guides, use plain English, explain what the reader can do, and keep examples easy to follow. Preserve commands, paths, links and the meaning of workflow rules when changing the wording.

## Versions and ownership

Keep the baseline in `AGENTS.md`, `.lean/README.md`, `.lean/lean/__init__.py` and the first numbered entry in `.lean/CHANGELOG.md` in sync (`lean lint` checks them), and update the root README.

MAJOR changes rules, canonical authority or paths an existing installation relies on. MINOR adds compatible capabilities or enforcement. PATCH clarifies wording. Keep historical changelog entries intact and explain migration before replacement.

See [.lean/CUSTOMIZING.md](.lean/CUSTOMIZING.md) for imports and project-owned files. Keep the workflow license notice when redistributing it.

## Describe the result

Fill in the PR Result Contract with the checks you ran, regression evidence where needed, review round and coverage, and anything still unverified. Passing tests alone does not complete semantic review. Commit, push, merge and release are separate actions when requested.
