# Contributing

Thanks for taking a look. This repository is the workflow template, and changes can reach projects that copy it. Keep changes portable, clear and backed by evidence.

Start with `AGENTS.md` and `.lean/README.md`. When instructions change, update the canonical contract and shared procedures together. Skill bodies live in `.lean/skills/`. Preserve the nine core discovery links and the ten optional skills' registration. Keep actual trackers, queue items, credentials and runtime state out of the template.

## Check the change

Run deterministic checks before review:

```sh
bash .lean/scripts/quality-gate.sh --root .
python3 -m unittest discover -s .lean/tests -p 'test_*.py'
```

The shared gate runs the commands in `.lean/PROJECT.md`, including ShellCheck, structure checks, hook tests, mode/catalog checks and gate/discovery tests. The full Python suite covers workflow behavior. Use temporary repositories for tests so the template stays free of task records.

Behavior changes need meaningful tests. For a bug fix, show its regression test failing before the fix and passing afterward. Review after validation; HIGH-depth work needs an independent reviewer.

For public guides, use plain English, explain what the reader can do, and keep examples easy to follow. Preserve commands, paths, links and the meaning of workflow rules when changing the wording.

## Versions and ownership

Keep the baseline in `.lean/README.md` and the first numbered entry in `.lean/CHANGELOG.md` in sync. Also update current baseline references in `AGENTS.md`, `.lean/PROJECT.md`, `.lean/CUSTOMIZING.md` and the root README.

MAJOR changes rules, canonical authority or paths an existing installation relies on. MINOR adds compatible capabilities or enforcement. PATCH clarifies wording. Keep historical changelog entries intact and explain migration before replacement. Unreleased changes stay labelled as Unreleased until released.

See [.lean/CUSTOMIZING.md](.lean/CUSTOMIZING.md) for imports and project-owned files. Keep the workflow license notice when redistributing it.

## Describe the result

Fill in the PR Result Contract with the checks you ran, regression evidence where needed, review round and coverage, and anything still unverified. Passing tests alone does not complete semantic review. Commit, push, merge and release are separate actions when requested.
