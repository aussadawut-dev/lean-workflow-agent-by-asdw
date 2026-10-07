# Release acquisition and recovery

The acquisition helper uses Git and Python standard-library tooling, writes only to a fresh private workspace outside Git checkouts, and does not modify the target or run release code. It uses isolated Git configuration, disables hooks/external transports and interactive prompts, and limits each Git call to 60 seconds. SSH host configuration still belongs to the user's runtime. Source override requires the user's explicit source choice; normal calls use the built-in Lean upstream URL.

```sh
python3 .lean/scripts/update_workflow.py /path/to/workflow-root --workspace /private/path/lean-update
# Optional explicit ref/source or known old installation:
python3 .lean/scripts/update_workflow.py /path/to/workflow-root --workspace /private/path/another-update --ref main --installed-ref <old-commit>
```

The helper selects numeric stable `vMAJOR.MINOR.PATCH`/`MAJOR.MINOR.PATCH` tags, ignoring prereleases. It handles annotated tags, refuses ambiguous short refs and accepts full commit SHAs. Full refs disambiguate tags/branches. Tag and AGENTS versions must agree; version regressions are refused even with an explicit ref. Older sources without a compatible release registry require a separately reviewed compatibility migration, not an implicit fallback. A failure may leave an external source checkout for diagnosis; retain it or choose a fresh workspace on retry. No target writes occur.

`release.json` records source URL, selected ref/commit, installed/incoming versions, baseline root, per-asset fingerprints and a suggested sibling migration session. Optional project-owned `.lean/upstream.json` supplies the previous commit when its source matches. `--installed-ref` overrides that hint; its checkout must match the installed baseline version. Previous content is comparison evidence, not proof that the current working tree is pristine. Read the previous registry to locate retired assets, which are not included in the incoming-only comparison list.

`status: INSPECT` always requires semantic reconciliation; even identical portable files do not prove settings/CI and extensions need no changes. The release report's `provenance` is the proposed exact `.lean/upstream.json` content, to be included in the approved takeover plan rather than written by acquisition.

Use the installed takeover helper and its tooling reference for inventory, cover/exclude, draft, check, stage, stage-check, seal, apply/resume, status and rollback:

```sh
python3 .lean/scripts/takeover.py inventory /path/to/workflow-root --session /private/path/lean-update/migration
python3 .lean/scripts/takeover.py draft --session /private/path/lean-update/migration --baseline /private/path/lean-update/source
```

Inventory and full-read attestations precede draft reconciliation. Do not apply the raw draft: it strips project additions. Save the reviewed plan, validate staging, obtain matching approval, then seal/apply using the exact commands in the takeover reference. Its snapshots, journal, locks, drift guards and refusal to overwrite later edits also cover upgrades. Retain an external copy of the trusted updater/recovery tools and direct imports before applying operations that change those tools. Recovery uses that same copy, not newly fetched code.

The helper's registry checker intentionally requires compatibility with the installed shared-assets/link schema. A future release that changes that schema is a visible blocker requiring a reviewed bootstrap decision. Do not patch the checker simply to admit unreviewed release paths.
