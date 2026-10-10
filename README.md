# Lean Workflow Agent by ASDW

A reusable GitHub template for working with coding agents through clear task contracts, meaningful tests, risk-based review and evidence before completion. Claude and Codex share one workflow, with optional tracking and task ownership. Bring your own application stack and choose how much process your project needs.

Current baseline: **4.1.0**. The template starts with unconfigured `standard` mode and `direct` execution; it contains no project tasks, queue items or leases.

## Workflow modes

| Mode | How work is managed | Useful when |
|---|---|---|
| `standard` | Task Contract → work → tests → validation → review → Quality Gate. Evidence stays in the session. | You want the core workflow with minimal record keeping. |
| `tracker` | Everything in standard, plus one workset document for each non-trivial task under `docs/tracking/`. | Decisions, progress and evidence need to survive between sessions. |
| `full` | Everything in tracker, plus queue items, scope ownership and local lease claims. | Multiple workers need explicit task ownership in one checkout. |

All three modes retain the same testing rules, quality floor and review requirements. A heavier mode adds coordination; it does not select a stronger model or a different quality level. Trivial tasks need no new tracker or queue item; work within an already claimed scope still follows ownership rules.

Execution is a separate choice:

| Execution | Who does the work |
|---|---|
| `direct` | The active agent implements and coordinates the task. This is the default. |
| `delegated` | The active agent acts as Controller and dispatches bounded work to a capable worker. |

Delegated execution requires available worker tooling. Parallel workers additionally require explicit user intent, independent tasks and exclusive file ownership. Independent HIGH-depth review is required with either execution setting.

## Detailed guides

| Topic | Contents |
|---|---|
| [Workflow overview](docs/workflow-overview.md) | Complete workflow sequence, validation, review and completion. |
| [Tracker](docs/tracker.md) | Workset creation, statuses, completion and mode upgrades/downgrades. |
| [Queue (Q)](docs/queue.md) | Full-mode ownership, claims, leases, dependencies and cleanup/history. |
| [Spawn and delegation](docs/spawn.md) | Codex/Claude Controller, worker and independent reviewer sequences. |
| [Model and effort](docs/models.md) | Provider selection sequences, session inheritance and model catalog refresh. |
| [Workflow takeover](docs/takeover-workflow.md) | Audit, user decisions, document migration and recoverable installation into another repo. |

## Getting started

### Requirements

Use macOS, Linux or WSL with Bash, Git and Python **3.9+**. Python tooling uses only the standard library; lease locking uses Unix `fcntl`. Install ShellCheck to run the workflow's own lint gate. Native Windows is unsupported.

Your coding agent and its runtime are supplied separately. The template has no application dependencies and requires no paid service of its own; agent access and usage follow your runtime's settings.

### Start a new project

Use GitHub's **Use this template** action if the repository is enabled as a template, or clone it and change the remote for your own repository:

```sh
git clone https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git my-project
cd my-project
```

To copy the files without this repository's Git history, an optional Node/npm-based route is:

```sh
npx degit aussadawut-dev/lean-workflow-agent-by-asdw my-project
cd my-project
git init
```

Open the project in Claude Code and run `/lean-init`, or invoke `$lean-init` in Codex. It discovers actual project facts and commands, records the selected mode/execution, and helps fill `.lean/PROJECT.md`.

Both runtimes read canonical skills in `.lean/skills/`, through per-skill discovery links. Nine core procedures are enabled by default; `python3 .lean/scripts/skill_pack.py enable` adds the seven maintenance procedures, and `disable` removes only their discovery links. Reload runtime skills after toggling. See [.lean/OPTIONAL.md](.lean/OPTIONAL.md). Edit the canonical files only; adding a Lean skill requires registering its canonical files and assigning it to core or optional discovery. If your runtime does not discover skills, ask the agent to read the relevant `SKILL.md` and follow its procedure. Other agents can follow `AGENTS.md` and the shared procedures manually; runtime integrations are provided for Claude and Codex.

### Configure without an agent

Choose one mode, then inspect and validate it:

```sh
python3 .lean/scripts/workflow.py configure standard
python3 .lean/scripts/workflow.py show
python3 .lean/scripts/workflow.py check
```

To enable tracking and delegation instead:

```sh
python3 .lean/scripts/workflow.py configure tracker --execution delegated
```

Omitting `--execution` preserves the current setting. Configuration belongs to the project in `.lean/config.json`; agents follow the recorded choice rather than selecting a mode for each task.

Fill `.lean/PROJECT.md` with your application's real test, lint, build and typecheck commands. Add gate commands between its existing markers, one command per line. Each must exit non-zero on failure. The shipped turn gate tests workflow integrity; the full regression suite runs before shipping behavior changes and in CI. Neither validates application code you add later. Missing/empty project gates block until configured.

### Keep workflow prose lean and clear

Enable the optional maintenance pack before invoking `/lean-compress` to remove repetition and filler while preserving the same rules and practical meaning. The [shared procedure](.lean/skills/lean-compress/SKILL.md) works for Claude and Codex from the same source. It uses clear, concise language and has no fixed compression ratio.

```text
/lean-compress workflow --preview
/lean-compress README.md --preview
/lean-compress README.md --apply
```

Preview is the default. `workflow` targets editable workflow prose; paths restrict which prose files may change. `--apply` requests changes within an approved scope. A matching approval is reused; a new scope or change to workflow behavior needs resolution before dependent edits. Reading a file never authorizes rewriting it.

**Read every corner of the workflow before compressing.** Inventory and fully read the canonical contract, router/policies, project facts, all skills/resources/discovery links, reviewer, hooks/settings, scripts/tests/templates, CI, README and history/ownership guidance. Record each file and revision in a coverage ledger. Large files must be read through EOF in chunks; listings, grep snippets, hashes and summaries do not establish coverage. An unread or inaccessible in-scope file blocks dependent compression. Exclude credentials, private settings, caches and runtime internals; report exclusions rather than claiming they were reviewed.

Then map the original rules to the proposed wording: actor, trigger, prerequisites, action, ordering, limits, exceptions, evidence and failure behavior. Keep frontmatter, imports, headings/anchors, code/Mermaid, inline code, commands, links, paths, identifiers, numeric limits, versions, gate markers and license notices unchanged. Code, tests, configuration and project history are read for context and stay outside prose compression. Preserve accepted project additions and unrelated pending edits.

Run preservation checks and the project Quality Gate, then review the actual diff at the required depth. Independent review is required for HIGH-risk areas; tests alone cannot prove preserved meaning. Report measured byte/word changes and any unread/unchanged targets. Do not claim token savings without measurement. This complete-read requirement applies to the compression audit, rather than changing context routing for ordinary tasks. The command does not publish changes or call a paid model API.

## Capabilities in detail

### One shared contract across agents

[AGENTS.md](AGENTS.md) is canonical. [CLAUDE.md](CLAUDE.md) imports it, and both runtimes discover nine core procedures through symlinks. Seven maintenance procedures are available as an optional discovery pack. No provider is the required primary agent; the active agent owns the task unless the project records a different Controller.

The contract requires acceptance evidence before reporting DONE, preserves an explicitly requested quality floor, and limits extra effort to work with a useful reason. Project-specific additions have dedicated sections so upgrades can preserve them.

### Planning, scope and decisions

A one-line Task Contract identifies risk, quality and observable acceptance before changes begin. The workflow supports reusing accepted scope, gathering evidence for alternatives and resolving material decisions before dependent implementation. Routine work within accepted scope needs no repeated approval.

Agents start with the smallest sufficient context. The policy router points them to deeper rules only when needed, and `.lean/PROJECT.md` supplies actual repository facts rather than an imposed stack or architecture.

### Meaningful tests and risk-based review

Behavior changes require meaningful tests. Bug fixes require a regression test demonstrated failing before the fix and passing afterward. Deterministic validation runs before semantic review.

Review depth follows the deeper of task risk and quality floor. HIGH-depth review requires an independent reviewer receiving the Task Contract and shipping diff without the author's reasoning. The review loop is bounded: after a second REWORK, one final pass must resolve the findings or report BLOCKED. A PASS ends that review cycle.

### Quality Gates and honest completion

Project-owned gate commands live in [.lean/PROJECT.md](.lean/PROJECT.md). Claude's Stop hook runs them; Codex follows the shared procedures and runs them explicitly.

Checks rerun by default, including on continued Stops after failure. Missing or empty gates block with an onboarding message. SessionStart records only a change baseline. `--cache-tree` is an explicit choice for checks whose inputs are entirely Git-visible; it does not cover environment or ignored dependencies.

This repository opts its Claude Stop hook into `--cache-tree`: an unchanged state reuses a passing run while contract and required review checks still run. Changed files or a previous refusal trigger fresh validation. After changing tools, environment or ignored dependencies, force a fresh run with `bash .lean/scripts/quality-gate.sh --root .` (include `--require-review --contract '<exact contract line>'` for HIGH work). Downstream projects should remove the Stop command's `--cache-tree` option when their checks depend on inputs outside Git-visible state.

The Claude adapter checks assistant contract provenance when transcript metadata is available. HIGH review receipts bind the reported review to the current contract and shipping state. Local hashes also catch changes to hooks/settings/gate commands until an already user-approved change is recorded. These mechanisms detect mistakes and stale evidence; an agent with write access can still alter them. Contract truth, regression timing, reviewer identity and task-record evidence remain procedural. Codex runs the checks explicitly; no native hook is claimed. See [.lean/policy/QUALITY.md](.lean/policy/QUALITY.md) for exact limits and commands.

All shared gate entry points hold a per-checkout lock for the lifetime of their checks. A busy or unavailable lock reports NOT_RUN; retry after the owning processes exit and never delete a live lock file. Direct validation commands outside the shared runner are not serialized. The lock does not freeze source edits or establish passing evidence.

Projects requiring enforcement outside the agent must use trusted CI and protected merge permissions. Local self-tests do not prove application correctness. Pre-existing/out-of-scope failures or unavailable required reviewers/workers remain BLOCKED with evidence.

### Repository cleanup

With the optional maintenance pack enabled, use `/lean-update-workflow [--ref <tag|branch|commit>]` to preview an upgrade from the Lean upstream stable tag. The [shared skill](.lean/skills/lean-update-workflow/SKILL.md) pins the commit, preserves project data/customizations, reconciles exact changes and uses external staging/snapshots for approved apply and recovery. Older or incompatible releases block writes. Project-owned `.lean/upstream.json` retains provenance; no commit, push or global configuration change is implied.

Use `/lean-clean-repo` to audit clutter and obsolete source, tests, dependencies, docs, assets, configuration, scripts and workflow files. Preview is the default. The [shared skill](.lean/skills/lean-clean-repo/SKILL.md) presents exact removals/reference edits, evidence, impact and checks before matching approval. Missing references alone do not prove a file is unused. Protected and uncertain candidates remain.

The [helper](.lean/scripts/clean_repo.py) inventories without writes and applies only a fingerprinted plan, retaining original bytes/modes in a private external recovery session. It preserves Git's index, blocks dirty/staged work, symlinks, nested repositories and protected state, and rejects drift/new descendants. Untracked work is preserved unless explicitly proposed with verified regeneration evidence (ordinary Python cache/OS debris is recognized). Apply/restore require repository writers stopped; a partial batch is journaled and recoverable. Restore refuses later edits. No automatic backup purge, commit or push occurs.

`apply <plan-id>` uses the previously presented session; `restore <session-path>` performs guarded recovery. See [tooling and proposal format](.lean/skills/lean-clean-repo/references/tooling.md). APPLIED still requires the project's checks and required review. Creating/installing this skill does not authorize cleaning any repository.

### Core and optional commands

All nine core procedures are user-invocable, including `lean-skill-effort`; the seven maintenance commands require the optional maintenance pack. Start ordinary work with `lean-task`; the agent handles scope, research, material decisions, implementation, review and completion checks as needed. It asks for unresolved material decisions or new scope approval, and preserves accepted decisions. You do not need to run each internal step yourself.

| Purpose | Claude Code | Codex skill invocation |
|---|---|---|
| Set up mode and execution | `/lean-init [standard\|tracker\|full] [--execution direct\|delegated]` | `$lean-init` with the same arguments |
| Start a task | `/lean-task <task description>` | `$lean-task <task description>` |
| Set procedure intensity | `/lean-skill-effort [standard\|high\|ultra\|reset] [lean-skill-name]` | `$lean-skill-effort` with the same arguments |
| Research a model catalog refresh | `/lean-model-update [codex\|claude\|all]` | `$lean-model-update` with the same arguments |
| Audit and shorten workflow prose | `/lean-compress [workflow\|PATH...] [--preview\|--apply]` | `$lean-compress` with the same arguments |
| Use an application submodule | `/lean-use-submodule <remote url>` | `$lean-use-submodule <remote url>` |
| Take over an existing workflow | `/lean-takeover-workflow "<target path>" [--preview\|--apply <plan-id>]` | `$lean-takeover-workflow` with the same arguments |
| Archive completed queue items | `/lean-clean-queue <old\|all> [--preview]` | `$lean-clean-queue` with the same arguments |
| Update installed Lean workflow | `/lean-update-workflow [--ref <ref>]` | `$lean-update-workflow` with the same arguments |
| Audit and clean repository files | `/lean-clean-repo [--path <path>]` | `$lean-clean-repo` with the same arguments |

For example:

```text
# Claude Code
/lean-task Add a regression test and fix the queue lease bug
/lean-compress workflow --preview
/lean-clean-queue old --preview

# Codex
$lean-task Add a regression test and fix the queue lease bug
$lean-compress workflow --preview
$lean-clean-queue old --preview
```

All discovered Lean skills are user-invocable and remain available to the agent, including scope, research, grill, review, gate and multi-agent. Nine core skills are discovered by default; enabling the maintenance pack exposes seven more. Command visibility does not change scope approval or execution routing.

In Codex CLI/IDE, select skills through `/skills` or mention them with `$`; use the available skill picker in Desktop. Keep implicit invocation enabled so the agent can follow the shared procedures. Examples elsewhere using `/name` describe Claude syntax; use the corresponding Codex skill invocation. No deprecated custom prompts or global installation are required. See [Claude skill invocation](https://code.claude.com/docs/en/skills) and [Codex skill invocation](https://learn.chatgpt.com/docs/build-skills).

Model refresh and compression still preview by default; applying a catalog proposal or compression requires its existing authorization checks. Queue cleanup with `old` or `all` authorizes archiving DONE items; `--preview` only shows the selection. Missing queue selection requires a choice. Command visibility grants no extra permissions, paid usage or Git publishing.

### Optional skill levels

All Lean procedures support `standard` (the existing default), `high` and `ultra` intensity under [.lean/policy/SKILL-EFFORT.md](.lean/policy/SKILL-EFFORT.md). Ask in natural language, for example: "use scope high, grill ultra and research high for this task" or "use ultra for all three skills". Task-specific requests remain in the task. Use `/lean-skill-effort high` to save a default, `/lean-skill-effort ultra lean-research` for an override, and `reset` to remove saved choices. No arguments inspects without writes. Settings are optional project-owned data, preserved on upgrades and kept in the selected target record root. Levels can differ per skill, and do not change workflow mode, quality, budget, model, execution or review requirements.

| Skill | high adds to standard | ultra adds to high |
|---|---|---|
| Scope | Detailed flows, rules, boundaries and acceptance per behavior | Material states, exceptions, failures and cross-flow consistency, with traceable validation |
| Grill | More questions by scope topic to find omissions and narrow requirements | Follow-up rounds, scenario details and confirmation of each important boundary |
| Research | More relevant vendors/approaches and corroborated decisive claims | Broader discovery, deeper comparison of leading candidates and conditional conclusions |
| Review | Trace callers, interfaces and relevant failure paths | Challenge consequential assumptions and cross-component invariants |
| Gate | Map acceptance criteria to current evidence and expose stale coverage | Cross-check scope, tests, review, tracker and queue consistency |

Higher levels reuse confirmed decisions and focus on relevant details. Grill asks in manageable batches; research distinguishes vendor breadth from source depth and reports evidence gaps. Findings can feed back into the scope, while approval and authority boundaries stay in force. These instructions guide agent behavior; repository checks validate the instruction contracts, not the accuracy of every future agent response.

### Runtime integration and limits

Claude's `.claude/settings.json` supplies SessionStart and Stop hooks, read-only Git permissions and `.env` read denies. These settings are Claude-specific; they do not configure Codex hooks or permissions and are not a general secret-protection guarantee. Keep secrets out of trackers, queue items and dispatch messages.

For headless Claude, follow your runtime's workspace trust and tool permission requirements. Other agents can follow the shared contract, but this repository does not provide native adapters for every runtime.

Workflow self-tests run locally and in GitHub Actions on Ubuntu with Python 3.9. They cover onboarding, modes, lease ownership, evidence/dependencies, downgrade guards, dry-run preservation, worker races, upgrade-back validation, canonical routing and discovery-link integrity. Smoke tests isolate reusable assets and preserve a configured host's project license and records. CI validates the workflow; add your application's own checks separately.

## Repository layout

```text
lean-workflow-agent-by-asdw/
├── AGENTS.md                      Shared contract and project additions
├── CLAUDE.md                      Claude entrypoint importing the contract
├── docs/                          User guides
│   ├── workflow-overview.md       Complete workflow sequence
│   ├── tracker.md                 Worksets and mode transitions
│   ├── queue.md                   Task ownership, leases and cleanup
│   ├── spawn.md                   Controller, worker and reviewer sequences
│   ├── models.md                  Model selection and reasoning effort
│   └── takeover-workflow.md       Audit, decisions and workflow migration
├── .lean/                         Portable workflow baseline
│   ├── PROJECT.md                 Project-owned facts, commands and gate
│   ├── config.json                Project-owned mode and execution choice
│   ├── README.md                  Policy router
│   ├── CUSTOMIZING.md             Import, ownership and upgrade guidance
│   ├── LICENSE                    Workflow notice for downstream imports
│   ├── CHANGELOG.md               Versions and migrations
│   ├── policy/                    Portable workflow rules
│   ├── skills/                    Canonical skills and resources
│   ├── roles/                     Shared reviewer instructions
│   ├── templates/                 Generic tracker and queue templates
│   ├── scripts/                   Shared gate, mode/lease tooling and checks
│   └── tests/                     Workflow behavior and regression tests
├── .claude/                       Claude runtime integration
│   ├── settings.json              Claude hook and permission settings
│   ├── hooks/                     SessionStart and Quality Gate hooks
│   ├── agents/
│   │   └── reviewer.md            Claude reviewer entrypoint
│   └── skills/                    Per-skill links to .lean/skills/
├── .agents/                       Codex integration
│   └── skills/                    Per-skill links to .lean/skills/
└── .github/                       GitHub integration
    ├── workflows/
    │   └── lean-workflow.yml       Workflow self-checks in CI
    └── pull_request_template.md   PR Result Contract template
```

Tracking and queue record directories are created by their mode setup; no example task history or runtime leases ship with the template.

## Importing, customizing and upgrading

For an existing project, follow [.lean/CUSTOMIZING.md](.lean/CUSTOMIZING.md). Merge entrypoints, settings, gitignore and CI. Preserve your project's owner, facts, accepted scope, configured mode/execution, gates, records, custom agents and skills.

Put shared project overrides below `## Project additions` in `AGENTS.md`; keep Claude-specific additions in `CLAUDE.md`. Retain [.lean/LICENSE](.lean/LICENSE) for the copied workflow alongside your own project license. Read [.lean/CHANGELOG.md](.lean/CHANGELOG.md) before crossing versions, especially the 2.x migration to shared AGENTS authority.

This README and CONTRIBUTING describe the template and may be replaced downstream. Workflow self-tests/CI can be removed if no longer wanted; remove their gate commands too. Keep mode tooling when tracker/full is used and retain a functioning application gate.

## Verify the workflow

Run from a Git working tree:

```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
.lean/tests/test-hooks.sh
python3 .lean/scripts/workflow.py --root . check
python3 .lean/scripts/model_catalog.py --root . check
python3 -m unittest discover -s .lean/tests -p 'test_*.py'
```

For contribution expectations, see [CONTRIBUTING.md](CONTRIBUTING.md). The project is distributed under the [MIT License](LICENSE); preserve its notice when redistributing the workflow.

### Keep workflow out of an application repository

Run `/lean-use-submodule <remote url>` from Lean to add or reuse the application under `targets/<repository-name>`. Lean stores `.gitmodules`, the gitlink and all workflow/project records; the application receives no agent workflow files. The command uses one shared skill discovered by both runtimes.

```sh
# Read-only preview; the skill applies a direct installation request.
python3 .lean/scripts/submodule.py use --dry-run -- https://github.com/team/my-project.git
python3 .lean/scripts/submodule.py use --apply -- https://github.com/team/my-project.git
python3 .lean/scripts/submodule.py context
```

Start sessions from Lean. The context reports `project_root` for application commands and Git, `record_root` for project facts/config and tracking, and `workflow_root` for tools/rules. Default workflow and model-catalog commands select the active records; `--root` overrides that selection. Explicit workflow record operations can add `--workflow-root` to source templates from Lean. Fill the returned project file with verified application checks, then run `python3 .lean/scripts/submodule.py gate`; Lean self-checks remain separate. Claude runs target checks before using its Lean cache, while Codex runs both gates explicitly.

Adding a submodule stages its registration; it does not commit or push. Initializing a registered submodule preserves its pinned commit: if the default branch differs, the command creates `codex/lean-<name>` at that commit rather than advancing the pointer. Commit application work inside the target and review the resulting pointer change in Lean separately. Checkout-local selection is ignored: after cloning Lean, rerun the command to initialize/select the registered target. `python3 .lean/scripts/submodule.py clear` deselects without removing its checkout or records. Live claims/active trackers block switching; use one active target per session. Existing checkout adoption, workflow removal from target history, and automatic pointer publishing are not part of this command.
