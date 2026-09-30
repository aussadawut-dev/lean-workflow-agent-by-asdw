# Changelog

Versions follow `MAJOR.MINOR.PATCH`. MAJOR changes workflow rules, or moves files an existing
install depends on. MINOR adds rules or files, and covers making an existing rule hold where it
was being bypassed -- the rule did not change, its enforcement did. PATCH clarifies wording.

## 2.3.0

`MODELS.md` has put the strongest model on `HIGH` risk review since the rule was written, and
nothing ever did it. `.claude/agents/reviewer.md` is `model: inherit` and no spawn site named a
model, so the rule was a no-op that announced nothing: a session on a fast model spawned a reviewer
on that same fast model for `HIGH` risk work, and the result reported review at `HIGH` depth --
true about the depth, silent about the reviewer. The evidence is structural and was checked on this
repository before the fix: `/lean-task` step 5, `/lean-review` step 4 and `CLAUDE.md`'s reviewer
line contained no mention of a model, and the new structure check below fails on all three of them
at the parent commit. For the absence half of that claim a scan is stronger than a run: no file
named a model, so the behavior could not have occurred. The enforcing half was run rather than
reasoned about -- this change's own `HIGH` review spawned the `reviewer` subagent with an explicit
model override, so the primary instruction is followable and not merely aspirational, and the
frontmatter's `model: inherit` is exactly what that spawn overrode.

- `/lean-review` step 4 and `/lean-task` step 5 spawn the reviewer on the strongest model available
  to the session. `CLAUDE.md` carries the same instruction, because it sends an agent to the
  reviewer without going through either skill -- the same reason it carries the round bound inline.
- Where the reviewer did not run on the strongest model available, the result says so. The report
  is conditioned on that outcome rather than on whether the model could be chosen: a session
  already running the strongest model inherits it and loses nothing, so reporting an inherited
  model as weaker would state something untrue. What is worth surfacing is the case this entry is
  about -- a reviewer no stronger than the author.
- `.claude/agents/reviewer.md` keeps `model: inherit`. Pinning the frontmatter would enforce the
  rule in one line and would break every install whose plan does not carry that model, in a
  repository whose whole purpose is to be copied into other projects. The frontmatter stays the
  fallback; the spawn site is where a model that depends on the session belongs.
- `.lean/scripts/check-structure.sh` fails if any of those three spawn sites stops naming the rule.
  A rule written in `policy/` and wired nowhere is exactly the failure above, and prose is the only
  place it can be wired, so a structural check is the only thing that holds it. The check reads the
  three known spawn sites by path and skips a file that no longer names the `reviewer` subagent in
  its code-span form: it is a gate command in every install, and the bare word is ordinary domain
  vocabulary, so guarding on it would block every turn in a project that dropped the bullet and
  writes about reviewers for any other reason. The anchor is the rule's phrase anywhere in the
  file rather than on the spawn line, because in `/lean-review` the two sit on different lines of
  wrapped prose: it catches the instruction being deleted, not a file that keeps the phrase
  elsewhere while dropping the instruction.

Review depth, risk rules, the round bound and the reviewer's own instructions are unchanged. MINOR
rather than MAJOR: the rule did not change, its enforcement did.

## 2.2.0

Review rounds are bounded. From this repository's own five-round run on one change, counted against
the branch rather than recalled: rounds 1 to 3 each returned `REWORK`, round 4 was the first
independent look at the regression fix and found seven things, round 5 found the fail-open described
below. One round followed a `PASS`, not two.

- A review cycle covers one Task Contract, and a change counts toward the cap when its motivation is
  a finding from that cycle's review. The most expensive round in that run came from taking on a
  second task mid-cycle: its new code introduced a regression that reopened the loop for the first
  task, and findings stopped mapping to a change. This rule separates the two, it does not shorten
  either.
- After the second `REWORK` on one contract, the cycle gets one last pass over the delta that fixes
  those findings, then stops. A capped cycle still holding a `REWORK` is `BLOCKED`, never `DONE`: a
  delta no reviewer has seen cannot satisfy condition 4 in `QUALITY.md`. Without that last pass a
  capped cycle would always ship its final fix unreviewed, and on this branch every round found
  something real in the previous round's fix, four times out of four.
- A `PASS` ends the review, and anything applied afterwards is new work with its own contract line.
  There is no carve-out for small fixes. Four were tried here and each one failed. "Cheap and clearly
  right" was unbounded, and on this branch that licence produced a real defect: round 4 passed, its
  seven advisory findings were applied, and one of them swapped a filesystem `grep -I` for
  `git grep -I`. Filesystem `grep` reads binary-ness from content; `git grep` honours
  `.gitattributes`, so a repository setting `*.md binary` skipped every markdown file while the scan
  reported clean -- a fail-open in a gate command every project runs on every turn. Round 5 caught
  it, and an unbounded rule means round 5 never happens, which makes this the rule that removes a
  round rather than the one above. Borrowing `WORKFLOW.md`'s trivial test failed the other way: it
  requires `LOW` risk and `CONTRACTS.md` makes every change inside a high-risk area `HIGH`, so it
  forbade fixing a typo in this file. "Comment or prose text" reopened the first hole, because the
  rules an agent follows are prose and `.lean/policy/` holds nothing else. Conditioning the prose
  half left the comment half: rewording the `<!-- gate:start -->` marker in `.lean/PROJECT.md` is a
  comment edit that turns the `Stop` hook into a silent no-op, verified. The carve-out went instead
  of gaining a fifth wording. What that costs depends on where the fix lands: where `WORKFLOW.md`'s
  trivial test can be met it is one contract line and no review, and inside a high-risk area it
  cannot be met at all, so a typo in one of these policy files costs a full `HIGH` cycle. That is the
  price of the area rather than of this rule -- the same price the borrowed trivial test charged --
  and it buys a rule with no wording left to argue with.

Run the corrected history through all three rules and the layout change is two `REWORK` rounds and
then a confirm pass, with the gate fix as its own short cycle. Round 3 found something real in round
2's fix, so that confirm pass plausibly returns `REWORK` too: three rounds ending `BLOCKED`, handed
to the user. That is the honest projection, not two rounds and done.

`REVIEW.md` has a `Rounds` section; `CLAUDE.md` carries both halves of the bound inline, because it
sends an agent to the `reviewer` subagent without going through the skill; `/lean-review` step 5
cites the section from the `PASS` and `REWORK` branches rather than restating it; `RECOVERY.md` lists
the capped case under `Blocked`, and `WORKFLOW.md` routes to the section. `QUALITY.md` condition 4
and `/lean-gate` now ask that review covered the delta that ships, not only that it ran at the right
depth -- `DONE` is decided on that path, and it does not read `REVIEW.md`. The round count goes in
the Result Contract's Evidence together with the range that review covered against the range that
ships, which `QUALITY.md` condition 4 now asks about. The pull request template prompts for both, so
they travel with the branch and a fresh session can recover them. Review depth is unchanged.

## 2.1.0

The Quality Gate no longer skips a turn just because the working tree is clean.

- `quality-gate.sh` decided whether to skip by asking whether the tree was dirty. Committing makes
  a tree clean, so an agent that changed files, committed them and ended its turn was never gated.
  That is the normal shape of a headless or CI run, and this hook is the only rule in the workflow
  that cannot be talked out of running. Verified before the fix, with a gate of `false`:
  uncommitted changes exited 2, the same changes committed exited 0.
- Skipping is now decided only by the recorded state, which already covered the commit, the
  uncommitted diff and untracked content. The clean-tree shortcut sat two lines above that
  comparison and returned before it was ever reached.
- `quality-gate.sh --seed` records the state and runs nothing; `session-start.sh` calls it. Without
  it, dropping the shortcut would make the gate run once per session even for a question that
  touched no files. If the SessionStart hook does not fire, the gate runs once at the first turn
  end rather than skipping -- the safe direction.
- A refused verdict now outlives the turn. A failing run records the state in
  `.claude/.gate-failed`, and seeding declines while that marker exists, so a new session cannot
  bless work the gate has already refused. Without it, seeding undid the fix after any SessionStart,
  and on a dirty broken tree it was worse than 2.0.0, which blocked. A passing run clears the
  marker. The marker is local state and gitignored, so it does not travel between checkouts and
  does not survive `git clean -xd`: after a clean, the next session starts with no memory of the
  refusal.
- `git ls-files --others -z | xargs -0 cat` in the state became a hazard once seed mode stopped
  draining stdin: with no untracked files, GNU xargs points the child's stdin at /dev/null but BSD
  xargs does not, so `cat` there would read the hook's own input. It is a read loop now.
- `check-structure.sh` gained three guards for this machinery: the gate's state files must be in
  `.gitignore` (otherwise each run's state includes the file the last run wrote and the gate never
  settles), `--seed` must not appear in `.claude/settings.json` (wiring it to Stop disables the gate
  in silence), and the retired-path scan now runs `git grep --untracked` rather than walking the
  working tree, so a vendored or ignored file naming a retired path cannot block a downstream
  project's every turn, while a new file a contributor has not staged yet is still covered. It
  matches text rather than references, so a project that owns a directory by either name should
  delete the check rather than satisfy it. `.gitignore` also covers `*.orig` and `*.rej` now: a
  conflicted merge of this very move is how such a file appears, and scanning untracked content
  would otherwise let it block the gate. The `.gitignore` entries are asked for by effect, via
  `git check-ignore`, so any equivalent pattern passes -- and both that and the scan need a git
  work tree, which the `npx degit` install route does not leave behind.
- `test-hooks.sh` is now 33 checks. Test 5 asserted "clean tree skips", which was the bug itself; it
  now asserts that committed work is gated. Every term of the state hash is covered: remove any one
  of the five and a check fails. Both guards that keep a refusal from being skipped are pinned
  separately, so removing either one fails a check even though the other would still hold.
  Restoring 2.0.0's clean-tree shortcut fails six.

**Upgrading to this from 2.0.0 or earlier:** if your Quality Gate currently fails, the first turn
after the upgrade will block, because the gate now runs on states it used to skip. `CLAUDE.md` tells
the agent not to repair a failure it did not cause, so it will report `BLOCKED` rather than fix it.
Clear the failure, or empty the gate block in `.lean/PROJECT.md`, before you start.

## 2.0.0

Every workflow path moved. Nothing about how work is done changed, but the versioning rule at the
top of this file was widened in the same commit: moving files an existing install depends on now
counts as MAJOR, which is what makes this 2.0.0 instead of a MINOR. An existing install needs the
migration steps below.

- `.agent/` is now `.lean/`: one namespace for the whole workflow, instead of rules in `.agent/`
  and self-checks in `.github/`.
- Self-checks left `.github/`, which now holds GitHub platform files only:
  - `.github/lean-workflow/check-structure.sh` -> `.lean/scripts/check-structure.sh`
  - `.github/lean-workflow/test-hooks.sh` -> `.lean/tests/test-hooks.sh`
- `check-structure.sh` gained three checks:
  - The scripts under `.lean/scripts/` and `.lean/tests/` are executable. This names a lost exec
    bit on `test-hooks.sh` instead of leaving it to CI. `check-structure.sh`'s own exec bit is not
    covered, because CI runs it by path and fails on permission before it can check anything.
  - The workflow version is present in both `.lean/README.md` and `.lean/CHANGELOG.md` and agrees.
    `.lean/PROJECT.md` is project-owned and free-form, so its version line is not read: a project
    whose own `PROJECT.md` says `Current version: 1.2.3` must not fail the workflow's checks.
  - `.agent/` and `.github/lean-workflow/` appear nowhere outside this file. Every text file is
    scanned, and the scan fails if it cannot complete rather than reading as clean. This check
    exists because the first attempt at this move left the root `README.md` pointing at both, and
    all three gate commands passed anyway -- the path check had just been repointed at the new
    namespace, so nothing was watching the old one.
- `CONTRIBUTING.md` and `.github/pull_request_template.md` added. The PR template is the Result
  Contract from `policy/CONTRACTS.md`, so the repository reports its own changes in the format it
  asks for.
- Zone names stay namespaced on purpose. A downstream project keeps its own `scripts/`, `tests/`,
  `docs/`, and root `CHANGELOG.md`, with nothing to rename and nothing to merge.
- Entries below describe the `.agent/` paths that were current when they were written. They are
  left as written.

### Migrating from 1.x

Run these **before** the `Upgrading` steps at the bottom of this file, not after. `git mv .agent
.lean` when `.lean` already exists does not fail: it nests the old tree at `.lean/.agent/`, your
`PROJECT.md` is no longer at `.lean/PROJECT.md`, and the `Stop` hook then silently does nothing,
because a missing `PROJECT.md` is a no-op by design.

1. `git mv .agent .lean`
2. `mkdir -p .lean/scripts .lean/tests`, then `git mv` `check-structure.sh` into `.lean/scripts/`
   and `test-hooks.sh` into `.lean/tests/`. Remove the empty `.github/lean-workflow/`.
3. Take the workflow-owned files from the 2.0.0 release instead of editing them; they already use
   the new paths. That is `.lean/README.md`, `.lean/CHANGELOG.md`, `.lean/policy/`,
   `.lean/scripts/`, `.lean/tests/`, `.claude/hooks/`, `.claude/skills/lean-*/`,
   `.claude/agents/reviewer.md`, and everything in `CLAUDE.md` above `## Project additions`.
   Also `AGENTS.md`, unless you edited it. If you edited any of the others, diff before
   overwriting. `.claude/settings.json` is not in this list: it names no retired path, and
   `Upgrading` step 6 has you merge it by hand.
4. Edit only what is yours. In `.lean/PROJECT.md` replace `.agent/` with `.lean/` and repoint the
   two script paths, including the ones inside its Quality Gate block. Do the same in your own
   `README.md` and any project file that named them.
5. Update `.github/workflows/lean-workflow.yml`: the two script paths, the `shellcheck` glob, and
   the `paths:` filters.
6. Confirm nothing was left behind, then validate:
   - `git grep -l -e '[.]agent/' -e '[.]github/lean-workflow/'` should list nothing but this file.
   - `ls .lean/.agent` should say no such directory.
   - `.lean/scripts/check-structure.sh` and `.lean/tests/test-hooks.sh` should both pass.

## 1.4.0

Changes from dogfooding (a Go CLI, 5 headless runs). The Task Contract was never written, `TESTING.md` was never read, and policy files were rarely opened outside skills. Rules that work are the ones in `CLAUDE.md` and the hooks.

- `CLAUDE.md` now carries the critical rules inline:
  - a one-line contract as the first line before changing files;
  - regression tests for bug fixes, shown failing before the fix and passing after;
  - no reading of workflow internals unless the task needs them.
- The Task Contract is one line at every risk and quality level. In round 2 the one-liner was written in 4/4 runs; the full block added nothing.
- `/lean-task` is shorter and loads policy files only when needed.
- Gate failures: fix only what your change caused. Pre-existing or out-of-scope failures are reported as `BLOCKED`, never patched under hook pressure. In round 2 the Stop hook pushed Claude into editing an unrelated test file.
- Gate commands must exit non-zero on failure. `/lean-init` and `PROJECT.md` say so, with the `gofmt` example.
- README note on headless and CI use.

## 1.3.0

- Self-checks for the workflow files in `.github/lean-workflow/`:
  - `test-hooks.sh` — Quality Gate and SessionStart hook behavior in throwaway git repos.
  - `check-structure.sh` — referenced paths exist, settings valid, hooks executable, skill/agent frontmatter, gate markers.
- CI `.github/workflows/lean-workflow.yml` runs ShellCheck and both scripts when workflow files change.

## 1.2.0

- Policy files moved to `.agent/policy/`. `.agent/PROJECT.md` stays as the only project-owned file, so upgrades can replace `policy/` as a whole.

## 1.1.0

- Claude-native layer in `.claude/`, pointing into `.agent/` with no rule duplication:
  - `reviewer` subagent for independent `HIGH` review.
  - Skills: `/lean-init`, `/lean-task`, `/lean-review`, `/lean-gate`.
  - `SessionStart` hook suggests `/lean-init` while `PROJECT.md` is empty.
  - Permissions: allow read-only git commands, deny reading `.env` files.

## 1.0.0

- Baseline #1: Task Contract, Quality Gate, risk-based testing and review, progressive context.
- `CLAUDE.md` canonical, `AGENTS.md` adapter.
- Defaults for quality, budget, and risk.
- `Stop` hook Quality Gate driven by `PROJECT.md`.

## Upgrading

Workflow files are separate from project files, so an upgrade replaces them without touching your code.

If you are crossing a MAJOR version, read that entry above and run its migration steps first. A
MAJOR moves paths, so the files step 1 names may not exist yet under the names it uses.

1. Replace `.lean/policy/`, `.lean/README.md`, `.lean/CHANGELOG.md`, `.lean/scripts/`, and `.lean/tests/`. Never replace `.lean/PROJECT.md`.
2. Replace `.claude/hooks/`, `.claude/agents/reviewer.md`, and `.claude/skills/lean-*/`. Keep your own agents and skills.
3. Replace `.github/workflows/lean-workflow.yml`, unless you deleted it. Take
   `.github/pull_request_template.md` too if you want it; it is new in 2.0.0 and yours to edit
   afterwards.
4. In `CLAUDE.md`, replace everything above `## Project additions`. Keep your additions.
5. Replace `AGENTS.md`, unless you edited it.
6. Merge `.claude/settings.json` by hand if you changed it.
7. Run `.lean/scripts/check-structure.sh` and `.lean/tests/test-hooks.sh`.
8. Re-read the new `CHANGELOG.md` entry and confirm nothing in it is still outstanding.
