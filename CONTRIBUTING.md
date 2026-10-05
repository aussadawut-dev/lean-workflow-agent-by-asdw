# Contributing

This repository is the workflow template, not an application. Changes reach downstream projects; keep them portable and backed by evidence.

Read `AGENTS.md` and `.lean/README.md` first. Update the canonical contract before adapters when shared instructions change. Keep Claude/Codex procedure bodies shared and preserve the eleven adapters' parity. Do not commit actual trackers, queue items, credentials or runtime state as template content.

Run the Quality Gate before review:

```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-hooks.sh
python3 .lean/scripts/workflow.py check
python3 -m unittest discover -s .lean/tests -p 'test_*.py'
```

New behavior needs meaningful tests. A bug fix demonstrates its regression test failing before the repair and passing afterward. Use temporary repositories for tests; do not initialize task records in this template to test modes. Run deterministic checks before semantic review and use independent review for HIGH depth.

Keep `.lean/README.md` and `.lean/CHANGELOG.md` versions synchronized. MAJOR changes rules, canonical authority or existing paths; describe migration before replacement. MINOR adds compatible capabilities/enforcement; PATCH clarifies wording. Preserve historical changelog entries. See `.lean/CUSTOMIZING.md` for project-owned files and imports/upgrades. Retain the workflow LICENSE notice when downstream users copy it.

Complete the PR Result Contract with checks, regression evidence, review round/coverage and unverified work. Passing checks do not substitute for semantic review or authorize publishing another project's data.
